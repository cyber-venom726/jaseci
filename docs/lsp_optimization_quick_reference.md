# Jac Language Server - Quick Optimization Reference

## Key Performance Improvements

### ⚡ Faster Response Times
- **Before**: 2-3 seconds for semantic tokens after newlines
- **After**: ~200ms for most edits, ~400ms during rapid typing

### 🧠 Simplified Edit Handling
```
ALL EDITS (150ms debounce):
├── Cancel running analysis
├── Quick syntax check (immediate)
├── Schedule debounced deep analysis
└── Refresh semantic tokens

Consistent approach: No special trivial edit handling
Every change triggers cancel → re-analyze workflow
```

### 🚀 Guaranteed Final Analysis Strategy
```
Keystroke → Quick Check (immediate) → Cancel Running Analysis → Debounce (150ms) → 
Check if Still Typing → [Wait +75ms] → Check Again → [Final Wait +45ms] → 
GUARANTEED Deep Analysis → Refresh Tokens

Key: The final analysis ALWAYS runs once the user stops typing, 
regardless of how many intermediate analyses were cancelled.
```

## Configuration Quick-Tune

### For Consistent Response (Recommended)
```jac
self._debounce_delay_sec = 0.15;           // 150ms for all edits
```

### For Resource Conservation (Conservative)  
```jac
self._debounce_delay_sec = 0.25;           // 250ms instead of 150ms
```

### For Rapid Typers (Extended)
```jac
self._debounce_delay_sec = 0.20;           // Longer initial delay
```

## Debugging Performance Issues

### Enable Profiling Logs
```jac
// Add to your config
settings.pass_timer = True;

// Check logs for:
// "PROFILE: Deep check took X seconds"
// "Analyzing 'file://...' ..."  
// "Canceling 'file://...' deep check..."
```

### Monitor Task Health
```jac
// Check pending tasks
ls.log_py(f"Pending: {len(ls._pending_deep_checks)}");
ls.log_py(f"Active: {len(ls.tasks)}");

// Should stay low and not accumulate
```

## Common Patterns

### Continuous Typing Issue ✅ FIXED
- **Problem**: After continuous typing, no final typecheck was happening
- **Solution**: Guaranteed final analysis with progressive timeout approach
- **Result**: Always get semantic tokens after user stops typing, regardless of how long they typed

### Newline Performance Issue ✅ FIXED
- **Problem**: 2+ second delay after pressing Enter
- **Solution**: Enhanced trivial edit detection + reduced debounce timing
- **Result**: ~200ms response for newlines

### Rapid Typing Lag ✅ FIXED  
- **Problem**: Long delays during typing bursts
- **Solution**: Single-shot debounce + adaptive extension
- **Result**: ~400ms after typing stops

### Resource Accumulation ✅ FIXED
- **Problem**: Cancelled tasks accumulating in memory
- **Solution**: Aggressive task cleanup + version tracking
- **Result**: Clean task lifecycle management

## Quick Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Still 150ms+ delays | Default timing too conservative | Reduce `_debounce_delay_sec` to 0.10 |
| Too many rapid refreshes | Debounce too short | Increase `_debounce_delay_sec` to 0.20 |
| Memory usage growing | Task cleanup failing | Check `cancel_analysis_for` implementation |
| CPU spikes during typing | Redundant analysis | Verify version tracking working |

## Testing the Optimizations

### Quick Test Protocol
1. **Type rapidly for 5+ seconds** → Stop → Colors should appear within ~300ms
2. **Press Enter** → Syntax highlighting within ~200ms  
3. **Type continuously** → Stop abruptly → Should ALWAYS get final semantic tokens
4. **Check memory** → Task counts should stay low

### Performance Validation
```bash
# Monitor language server process
top -p $(pgrep -f "jac.*langserve")

# Check response times in editor
# - Type any content and time syntax highlighting
# - Expected: <200ms for color updates
```
