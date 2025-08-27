# Memory Optimization Guide for PySide6 Labeler

## Overview
The PySide6 Labeler application has been enhanced with comprehensive memory management features to handle large datasets efficiently. This guide provides tips and best practices for optimal performance.

## Memory Management Features

### 1. Adaptive Memory Limits
- **System Detection**: Automatically detects available system memory
- **Dynamic Limits**: Adjusts memory limits based on system capacity (25% of system memory, max 1GB)
- **Conservative Defaults**: Reduced default limits for better stability

### 2. Chunked Data Loading
- **Large File Detection**: Automatically detects files >50MB (CSV) or >5000 rows (Excel)
- **Progressive Loading**: Loads data in smaller chunks (500 rows by default)
- **Load More Feature**: Allows loading additional data as needed

### 3. Image Cache Management
- **Limited Cache Size**: Caches only 5 recent images by default
- **Automatic Cleanup**: Clears cache when memory usage is high
- **Thumbnail Generation**: Creates optimized thumbnails for better performance

### 4. Proactive Memory Monitoring
- **Early Intervention**: Triggers cleanup at 70% memory usage
- **Multiple Cleanup Levels**: Different strategies for different memory levels
- **Garbage Collection**: Forces Python garbage collection when needed

## Memory Menu Options

### Clear Image Cache
- Immediately frees memory used by cached images
- Use when working with many images

### Memory Info
- Shows current memory usage statistics
- Displays cache sizes and data counts

### Load More Data
- Loads additional data chunks for large files
- Useful when working with datasets larger than initial chunk

### Force Memory Cleanup
- Performs aggressive memory cleanup
- Runs multiple garbage collection cycles
- Clears all temporary data

### Optimize Memory Settings
- Automatically adjusts settings based on current system state
- Recommends optimal chunk sizes and cache limits

## Best Practices

### 1. For Large Datasets (>10,000 rows)
- Use the "Load More" feature instead of loading everything at once
- Work with filtered subsets when possible
- Clear image cache frequently
- Use the "Force Memory Cleanup" option periodically

### 2. For Image-Heavy Work
- Reduce image cache size in settings
- Use "Clear Image Cache" frequently
- Consider working with smaller image sets

### 3. For Memory-Constrained Systems (<8GB RAM)
- Use smaller chunk sizes (250-500 rows)
- Reduce table display limits
- Monitor memory usage with the Memory Info tool
- Close other applications when possible

### 4. General Tips
- Use filters to work with smaller data subsets
- Save work frequently to avoid data loss
- Restart the application if memory usage becomes excessive
- Use the memory monitoring script for continuous monitoring

## Memory Monitoring Script

A separate `memory_monitor.py` script is provided for monitoring memory usage:

```bash
# Check current memory status
python memory_monitor.py

# Monitor memory for 60 seconds
python memory_monitor.py monitor 60

# Monitor with custom interval (every 10 seconds)
python memory_monitor.py monitor 120 10
```

## Troubleshooting High Memory Usage

### Symptoms
- Application becomes slow or unresponsive
- "Memory usage is high" warnings appear
- System becomes sluggish

### Solutions
1. **Immediate Actions**:
   - Use "Clear Image Cache" from Memory menu
   - Use "Force Memory Cleanup" from Memory menu
   - Close unnecessary applications

2. **Data Management**:
   - Use filters to work with smaller datasets
   - Load data in smaller chunks
   - Save and restart if working with very large files

3. **Settings Optimization**:
   - Use "Optimize Memory Settings" from Memory menu
   - Reduce chunk size for large files
   - Reduce image cache size

4. **System Level**:
   - Close other memory-intensive applications
   - Restart the application if memory usage is excessive
   - Consider upgrading system memory for very large datasets

## Performance Settings

### Default Settings (Adaptive)
- **Memory Limit**: 25% of system memory (max 1GB)
- **Chunk Size**: 500 rows
- **Table Display**: 2000 rows max
- **Image Cache**: 5 images

### Low Memory Systems (<4GB RAM)
- **Memory Limit**: 512MB
- **Chunk Size**: 250 rows
- **Table Display**: 1000 rows max
- **Image Cache**: 3 images

### High Memory Systems (>8GB RAM)
- **Memory Limit**: 1GB
- **Chunk Size**: 1000 rows
- **Table Display**: 3000 rows max
- **Image Cache**: 8 images

## Technical Details

### Memory Usage Breakdown
- **DataFrame**: ~50-80% of memory usage
- **Image Cache**: ~10-30% of memory usage
- **UI Components**: ~5-10% of memory usage
- **System Overhead**: ~5-10% of memory usage

### Optimization Strategies
- **Lazy Loading**: Load data only when needed
- **View vs Copy**: Use DataFrame views instead of copies when possible
- **Garbage Collection**: Force cleanup at strategic points
- **Cache Management**: Limit and clear caches proactively

## Support

If you continue to experience memory issues:
1. Check the log output for memory-related messages
2. Use the memory monitoring script to track usage patterns
3. Consider working with smaller datasets or using more aggressive filtering
4. Report issues with specific file sizes and system specifications
