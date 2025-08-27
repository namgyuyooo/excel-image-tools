#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psutil
import os
import sys
import time
from typing import Dict, List

def get_memory_info() -> Dict[str, float]:
    """Get comprehensive memory information"""
    try:
        vm = psutil.virtual_memory()
        return {
            'total_mb': vm.total / 1024 / 1024,
            'available_mb': vm.available / 1024 / 1024,
            'used_mb': vm.used / 1024 / 1024,
            'percent': vm.percent,
            'free_mb': vm.free / 1024 / 1024
        }
    except Exception:
        return {
            'total_mb': 8192,  # Default 8GB
            'available_mb': 4096,
            'used_mb': 4096,
            'percent': 50.0,
            'free_mb': 4096
        }

def get_process_memory(pid: int = None) -> float:
    """Get memory usage for specific process or current process"""
    try:
        if pid is None:
            pid = os.getpid()
        process = psutil.Process(pid)
        return process.memory_info().rss / 1024 / 1024  # MB
    except Exception:
        return 0.0

def get_recommendations(memory_info: Dict[str, float], process_memory: float) -> List[str]:
    """Get memory optimization recommendations"""
    recommendations = []
    
    # System memory recommendations
    if memory_info['percent'] > 90:
        recommendations.append("⚠️  CRITICAL: System memory usage is very high (>90%)")
        recommendations.append("   - Close unnecessary applications")
        recommendations.append("   - Restart the application")
    elif memory_info['percent'] > 80:
        recommendations.append("⚠️  WARNING: System memory usage is high (>80%)")
        recommendations.append("   - Consider closing other applications")
    
    # Process memory recommendations
    if process_memory > 1024:
        recommendations.append("⚠️  Process using >1GB memory")
        recommendations.append("   - Use 'Load More' feature instead of loading all data")
        recommendations.append("   - Clear image cache frequently")
    elif process_memory > 512:
        recommendations.append("ℹ️  Process using >500MB memory")
        recommendations.append("   - Monitor memory usage")
    
    # General recommendations
    if memory_info['available_mb'] < 1024:
        recommendations.append("💡 TIP: Less than 1GB available memory")
        recommendations.append("   - Reduce chunk size in application settings")
        recommendations.append("   - Work with smaller datasets")
    
    if not recommendations:
        recommendations.append("✅ Memory usage is within normal limits")
    
    return recommendations

def monitor_memory(duration: int = 60, interval: int = 5):
    """Monitor memory usage for specified duration"""
    print(f"Monitoring memory for {duration} seconds (every {interval}s)...")
    print("=" * 60)
    
    start_time = time.time()
    max_process_memory = 0.0
    
    while time.time() - start_time < duration:
        memory_info = get_memory_info()
        process_memory = get_process_memory()
        max_process_memory = max(max_process_memory, process_memory)
        
        print(f"\n[{time.strftime('%H:%M:%S')}] Memory Status:")
        print(f"  System: {memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.0f}MB ({memory_info['percent']:.1f}%)")
        print(f"  Available: {memory_info['available_mb']:.1f}MB")
        print(f"  Process: {process_memory:.1f}MB")
        
        recommendations = get_recommendations(memory_info, process_memory)
        for rec in recommendations:
            print(f"  {rec}")
        
        if time.time() - start_time < duration - interval:
            time.sleep(interval)
    
    print("\n" + "=" * 60)
    print(f"Monitoring completed. Max process memory: {max_process_memory:.1f}MB")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "monitor":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            monitor_memory(duration, interval)
        elif sys.argv[1] == "status":
            memory_info = get_memory_info()
            process_memory = get_process_memory()
            
            print("Current Memory Status:")
            print(f"System Memory: {memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.0f}MB ({memory_info['percent']:.1f}%)")
            print(f"Available Memory: {memory_info['available_mb']:.1f}MB")
            print(f"Process Memory: {process_memory:.1f}MB")
            
            recommendations = get_recommendations(memory_info, process_memory)
            print("\nRecommendations:")
            for rec in recommendations:
                print(f"  {rec}")
        else:
            print("Usage:")
            print("  python memory_monitor.py status          # Show current status")
            print("  python memory_monitor.py monitor [duration] [interval]  # Monitor for duration seconds")
    else:
        # Default: show current status
        memory_info = get_memory_info()
        process_memory = get_process_memory()
        
        print("Memory Status:")
        print(f"System: {memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.0f}MB ({memory_info['percent']:.1f}%)")
        print(f"Available: {memory_info['available_mb']:.1f}MB")
        print(f"Process: {process_memory:.1f}MB")
        
        recommendations = get_recommendations(memory_info, process_memory)
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"  {rec}")

if __name__ == "__main__":
    main()
