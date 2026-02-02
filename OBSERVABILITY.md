# Observability & Instrumentation

> How go-optimizr tracks memory, performance, and system health in real-time.

[![Metrics](https://img.shields.io/badge/Metrics-46%20Fields-blue)](https://shields.io)
[![Memory](https://img.shields.io/badge/Memory-30s%20Snapshots-green)](https://shields.io)
[![Export](https://img.shields.io/badge/Export-JSON-orange)](https://shields.io)

---

## Why This Matters

**For recruiters and hiring managers:** This instrumentation layer demonstrates:

1. **Production Awareness** — Real systems need monitoring; I built it in from day one
2. **Memory Leak Detection** — The 30-second snapshot system can identify leaks before they cause OOM
3. **Data-Driven Optimization** — Every design decision (w=3 workers) came from this data
4. **Export-Ready Metrics** — JSON output integrates with existing observability stacks

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INSTRUMENTATION ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────┐                                                     │
│  │     Worker Pool    │                                                     │
│  │  ┌─────┐ ┌─────┐   │                                                     │
│  │  │ W1  │ │ W2  │   │  Per-image metrics                                  │
│  │  └──┬──┘ └──┬──┘   │  (input/output bytes, duration, errors)             │
│  │     │      │       │                                                     │
│  │  ┌──▼──────▼──┐    │                                                     │
│  │  │    W3      │    │                                                     │
│  │  └─────┬──────┘    │                                                     │
│  └────────┼───────────┘                                                     │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         ANALYTICS COLLECTOR                          │   │
│  │                       (internal/analytics/collector.go)              │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   Timing     │  │    File      │  │    Size      │               │   │
│  │  │   Metrics    │  │   Metrics    │  │   Metrics    │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ • StartTime  │  │ • Processed  │  │ • InputBytes │               │   │
│  │  │ • EndTime    │  │ • Failed     │  │ • OutputBytes│               │   │
│  │  │ • Duration   │  │ • Total      │  │ • BytesSaved │               │   │
│  │  │ • Avg/Min/Max│  │ • ErrorRate  │  │ • Ratio      │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   Memory     │  │     GC       │  │   Analysis   │               │   │
│  │  │   Monitor    │  │   Tracker    │  │    Engine    │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ • 30s ticker │  │ • Run count  │  │ • CPU/IO     │               │   │
│  │  │ • Snapshots  │  │ • Pause avg  │  │ • Stability  │               │   │
│  │  │ • Peak track │  │ • Pause max  │  │ • Recommend  │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           OUTPUT LAYER                               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   Console    │  │    JSON      │  │ Prometheus   │               │   │
│  │  │   Report     │  │   Export     │  │  (planned)   │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ Box-drawing  │  │ summary.json │  │ /metrics     │               │   │
│  │  │ formatting   │  │ 46 fields    │  │ endpoint     │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Collector (`internal/analytics/collector.go`)

### Key Components

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Timing Metrics** | Track execution duration | `atomic.Int64` for start/end timestamps |
| **File Metrics** | Count processed/failed | `atomic.AddInt64` for lock-free updates |
| **Size Metrics** | Track compression | `atomic.AddInt64` for bytes in/out |
| **Memory Monitor** | Detect leaks | Background goroutine with 30s ticker |
| **GC Tracker** | Measure pause impact | Extracts from `runtime.MemStats` |
| **Analysis Engine** | Generate insights | Algorithmic analysis of collected data |

### Thread Safety Model

All metrics use `sync/atomic` for lock-free concurrent updates:

```go
// From collector.go - lock-free metric updates
func (c *Collector) RecordConversion(inputBytes, outputBytes int64, duration time.Duration) {
    atomic.AddInt64(&c.ProcessedFiles, 1)
    atomic.AddInt64(&c.TotalInputBytes, inputBytes)
    atomic.AddInt64(&c.TotalOutputBytes, outputBytes)

    // Compare-and-swap for min/max tracking
    for {
        current := atomic.LoadInt64(&c.MinProcessingTime)
        if current <= duration.Nanoseconds() && current != 0 {
            break
        }
        if atomic.CompareAndSwapInt64(&c.MinProcessingTime, current, duration.Nanoseconds()) {
            break
        }
    }
}
```

**Why atomic > mutex?**
- **5ns** per atomic operation vs **25ns** per mutex lock/unlock
- No deadlock risk
- No contention—workers never block each other

---

## Memory Monitoring System

### How Memory Leak Detection Works

```go
// Background goroutine captures memory state every 30 seconds
func (c *Collector) memoryMonitor() {
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ticker.C:
            c.captureMemorySnapshot()
        case <-c.stopChan:
            return
        }
    }
}

// Each snapshot captures full memory state
func (c *Collector) captureMemorySnapshot() {
    var memStats runtime.MemStats
    runtime.ReadMemStats(&memStats)

    snapshot := MemorySnapshot{
        Timestamp:  time.Now(),
        AllocMB:    float64(memStats.Alloc) / (1024 * 1024),
        TotalAlloc: float64(memStats.TotalAlloc) / (1024 * 1024),
        SysMB:      float64(memStats.Sys) / (1024 * 1024),
        HeapInUse:  float64(memStats.HeapInuse) / (1024 * 1024),
        NumGC:      memStats.NumGC,
        GCPauseMs:  float64(memStats.PauseNs[(memStats.NumGC+255)%256]) / 1e6,
    }

    c.mu.Lock()
    c.MemSnapshots = append(c.MemSnapshots, snapshot)
    c.mu.Unlock()
}
```

### Memory Stability Analysis

The collector analyzes snapshots to determine memory health:

```go
func (c *Collector) analyzeMemoryStability() (bool, float64, float64, float64) {
    if len(c.MemSnapshots) < 2 {
        return true, 0, 0, 0
    }

    var min, max float64 = math.MaxFloat64, 0

    for _, snap := range c.MemSnapshots {
        if snap.AllocMB < min {
            min = snap.AllocMB
        }
        if snap.AllocMB > max {
            max = snap.AllocMB
        }
    }

    memRange := max - min
    stable := memRange < 500  // Stable if range < 500MB

    return stable, min, max, memRange
}
```

**Leak Detection Heuristic:**
- `range < 500 MB` → Memory stable, no leak
- `range > 500 MB` with upward trend → Potential leak, investigate

---

## Metrics Reference

### Complete JSON Schema (`summary.json`)

```json
{
  // === TIMING ===
  "start_time": "2024-01-15T10:30:00Z",
  "end_time": "2024-01-15T10:33:25Z",
  "duration": "3m25s",
  "duration_seconds": 205.0,

  // === FILE STATISTICS ===
  "total_files": 1246,
  "processed_files": 1246,
  "failed_files": 0,
  "error_rate_percent": 0.0,

  // === SIZE METRICS ===
  "total_input_bytes": 10748573491,
  "total_output_bytes": 404125184,
  "total_input_gb": 10.01,
  "total_output_gb": 0.38,
  "bytes_saved": 10344448307,
  "space_saving_percent": 96.2,
  "compression_ratio": 26.6,

  // === PERFORMANCE ===
  "avg_processing_time_ms": 492.21,
  "min_processing_time_ms": 82.57,
  "max_processing_time_ms": 1530.22,
  "throughput_mb_per_sec": 49.99,
  "images_per_second": 6.08,

  // === MEMORY ===
  "peak_memory_alloc_mb": 319.0,
  "peak_memory_sys_mb": 774.57,
  "memory_stable": true,
  "memory_min_mb": 0.23,
  "memory_max_mb": 319.0,
  "memory_range_mb": 318.77,

  // === GARBAGE COLLECTION ===
  "total_gc_runs": 722,
  "avg_gc_pause_ms": 0.06,
  "max_gc_pause_ms": 0.10,
  "gc_pause_total_ms": 43.32,

  // === ANALYSIS ===
  "cpu_bound_analysis": "Balanced: System shows good balance between CPU and I/O. Current worker count appears optimal.",
  "recommendations": [
    "Processing time variance is high (avg: 492ms, max: 1530ms). This may indicate GC pauses or I/O contention.",
    "Consider increasing worker count if CPU utilization is below 70%."
  ],

  // === RAW MEMORY SNAPSHOTS ===
  "memory_snapshots": [
    {
      "timestamp": "2024-01-15T10:30:30Z",
      "alloc_mb": 45.2,
      "total_alloc_mb": 1203.4,
      "sys_mb": 412.0,
      "heap_inuse_mb": 52.1,
      "num_gc": 89,
      "gc_pause_ms": 0.05
    },
    // ... snapshots every 30 seconds
  ]
}
```

---

## Console Report

When running with `-verbose`, the collector outputs a formatted report:

```
╔═══════════════════════════════════════════════════════════════╗
║              DEEP ANALYTICS REPORT                            ║
╠═══════════════════════════════════════════════════════════════╣
║ EXECUTION                                                     ║
║   Duration:              3m25s                                 ║
║   Start:                 2024-01-15 10:30:00                   ║
║   End:                   2024-01-15 10:33:25                   ║
╠═══════════════════════════════════════════════════════════════╣
║ FILE STATISTICS                                               ║
║   Total Files:           1246                                  ║
║   Processed:             1246                                  ║
║   Failed:                0                                     ║
║   Error Rate:            0.00%                                 ║
╠═══════════════════════════════════════════════════════════════╣
║ SIZE METRICS                                                  ║
║   Input Size:            10.01 GB                             ║
║   Output Size:           0.38 GB                              ║
║   Space Saved:           9.63 GB                              ║
║   Compression:           96.2%                                 ║
║   Compression Ratio:     26.6x                                ║
╠═══════════════════════════════════════════════════════════════╣
║ PERFORMANCE METRICS                                           ║
║   Avg Time/Image:        492.21 ms                            ║
║   Min Time/Image:        82.57 ms                             ║
║   Max Time/Image:        1530.22 ms                           ║
║   Throughput:            49.99 MB/s                           ║
║   Images/Second:         6.08                                  ║
╠═══════════════════════════════════════════════════════════════╣
║ MEMORY ANALYSIS                                               ║
║   Peak Heap:             319.00 MB                            ║
║   Peak System:           774.57 MB                            ║
║   Memory Stable:         true                                  ║
║   Range:                 0.23 MB - 319.00 MB (range: 318.77 MB)║
╠═══════════════════════════════════════════════════════════════╣
║ GC ANALYSIS                                                   ║
║   Total GC Runs:         722                                   ║
║   Avg GC Pause:          0.06 ms                              ║
║   Max GC Pause:          0.10 ms                              ║
╠═══════════════════════════════════════════════════════════════╣
║ CPU/IO ANALYSIS                                               ║
║   Balanced: System shows good balance between CPU and I/O.     ║
║   Current worker count appears optimal.                        ║
╠═══════════════════════════════════════════════════════════════╣
║ RECOMMENDATIONS                                               ║
║   1. Processing time variance is high (avg: 492ms, max:        ║
║      1530ms). This may indicate GC pauses or I/O contention.   ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## How to Use This Data

### 1. Detecting Memory Leaks

```bash
# Run a long job and check memory stability
./go-optimizr -input ./large-dataset -output ./output -verbose

# Check the summary
cat output/summary.json | jq '.memory_stable, .memory_range_mb'
# Expected: true, <500
```

If `memory_stable: false` or `memory_range_mb > 500`, investigate the snapshots:

```bash
# Plot memory over time
cat output/summary.json | jq '.memory_snapshots[] | [.timestamp, .alloc_mb]' | ...
```

### 2. Tuning Worker Count

```bash
# Compare throughput across configurations
for w in 1 2 3 4 6; do
  ./go-optimizr -input ./test-images -output ./output-w$w -workers $w
  echo "w=$w: $(cat output-w$w/summary.json | jq '.images_per_second')"
done
```

### 3. Identifying I/O vs CPU Bottlenecks

Check the `cpu_bound_analysis` field:

| Analysis Result | Meaning | Action |
|-----------------|---------|--------|
| "CPU Bound" | Workers competing for CPU | Reduce worker count |
| "I/O Bound" | Workers waiting on disk | Increase workers or use faster storage |
| "Balanced" | Optimal configuration | Keep current settings |

### 4. Integration with Grafana/Prometheus (Future)

The JSON schema is designed for easy conversion to Prometheus metrics:

```yaml
# Proposed prometheus.yml scrape config
scrape_configs:
  - job_name: 'go-optimizr'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
```

Planned metrics endpoint would expose:
```
# HELP go_optimizr_processed_files_total Total files processed
# TYPE go_optimizr_processed_files_total counter
go_optimizr_processed_files_total 1246

# HELP go_optimizr_compression_ratio Current compression ratio
# TYPE go_optimizr_compression_ratio gauge
go_optimizr_compression_ratio 26.6

# HELP go_optimizr_memory_alloc_bytes Current heap allocation
# TYPE go_optimizr_memory_alloc_bytes gauge
go_optimizr_memory_alloc_bytes 334495744
```

---

## Code Navigation

| File | Lines | Purpose |
|------|-------|---------|
| `internal/analytics/collector.go` | 1-100 | Struct definitions, constructor |
| `internal/analytics/collector.go` | 101-200 | Memory monitoring goroutine |
| `internal/analytics/collector.go` | 201-300 | Metric recording (atomic ops) |
| `internal/analytics/collector.go` | 301-400 | Analysis algorithms |
| `internal/analytics/collector.go` | 401-500 | JSON export |
| `internal/analytics/collector.go` | 501-578 | Console report formatting |

**Key functions to review:**

```go
// Start the memory monitoring background goroutine
func (c *Collector) Start()

// Record a single image conversion (called by workers)
func (c *Collector) RecordConversion(inputBytes, outputBytes int64, duration time.Duration)

// Stop monitoring and finalize metrics
func (c *Collector) Stop()

// Generate analysis and recommendations
func (c *Collector) Analyze() AnalysisResult

// Export to JSON file
func (c *Collector) ExportJSON(path string) error

// Print formatted console report
func (c *Collector) PrintSummary()
```

---

## Design Decisions

### Why 30-Second Snapshot Interval?

| Interval | Pros | Cons |
|----------|------|------|
| 1 second | High resolution | CPU overhead, large JSON |
| **30 seconds** | **Balance of detail and overhead** | **Chosen** |
| 5 minutes | Minimal overhead | May miss short spikes |

30 seconds captures:
- Memory trends over multi-minute runs
- GC pause patterns
- Leak detection with sufficient granularity

### Why Atomic Operations Over Mutex?

For high-frequency metrics (called per-image):

```go
// This is called 6+ times per second
atomic.AddInt64(&c.ProcessedFiles, 1)  // 5ns, no blocking

// vs mutex alternative
c.mu.Lock()                            // 25ns + potential contention
c.ProcessedFiles++
c.mu.Unlock()
```

For low-frequency operations (memory snapshots), mutex is acceptable:

```go
c.mu.Lock()  // Only called every 30 seconds
c.MemSnapshots = append(c.MemSnapshots, snapshot)
c.mu.Unlock()
```

---

## Summary

This instrumentation layer demonstrates:

1. **Lock-free concurrent metrics** using atomic operations
2. **Background monitoring** with graceful shutdown
3. **Automated analysis** that generates actionable recommendations
4. **Export-ready format** for integration with existing tools
5. **Production mindset** — observability built-in, not bolted-on

For interviews, this code shows you understand that **shipping code is not the same as shipping production code**—production code needs to be observable.
