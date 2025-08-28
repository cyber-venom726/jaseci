# Migration Guide: Jac Language Server Performance Optimizations

## Overview
This guide helps you understand and adopt the performance optimizations made to the Jac Language Server debounce and scheduling system.

## What Changed

### 🔧 Core Timing Improvements
| Parameter | Before | After | Impact |
|-----------|--------|-------|---------|
| Primary debounce | 300ms | 150ms | 2x faster response |
| Trivial edit interval | 1200ms | 600ms | More responsive newlines |
| Scheduling strategy | Recursive | Single-shot | Cleaner task management |

### 🚀 Enhanced Features
- **Intelligent Edit Classification**: Different timing for trivial vs structural edits
- **Improved Cancellation**: Aggressive cleanup prevents resource accumulation  
- **Better Trivial Detection**: Recognizes more patterns as non-semantic
- **Adaptive Extensions**: Single extension instead of recursive delays

## Breaking Changes

### ⚠️ API Changes
```jac
// OLD: Basic scheduling
def schedule_deep_check(self: JacLangServer, file_path: str) -> None

// NEW: Enhanced with optional parameters (backward compatible)
def schedule_deep_check(
    self: JacLangServer, 
    file_path: str, 
    edit_type: str = 'semantic',     // NEW: optional
    impact_score: float = 0.5        // NEW: optional  
) -> None
```

### 🔄 Configuration Changes
```jac
// NEW: Additional configuration parameters
class JacLangServer {
    // Existing (modified values)
    self._debounce_delay_sec: float = 0.15;           // Was 0.30
    self._min_interval_for_trivial_sec: float = 0.6;  // Was 1.2
    
    // NEW: Additional tracking
    self._analysis_version: <>dict[(str, int)] = {};
    self._active_version: <>dict[(str, int)] = {};
}
```

## Migration Steps

### Step 1: Update Timing Configuration
```jac
// OLD configuration
self._debounce_delay_sec: float = 0.30;
self._min_interval_for_trivial_sec: float = 1.2;

// NEW optimized configuration
self._debounce_delay_sec: float = 0.15;  // 2x faster
self._min_interval_for_trivial_sec: float = 0.6;  // More responsive
```

### Step 2: Enhanced Trivial Edit Detection
```jac
// OLD: Basic whitespace detection
if text.strip() == '' and ('\n' in text or '\r' in text or text.isspace()) {
    is_trivial = True;
}

// NEW: Comprehensive detection
stripped_text = text.strip();
is_trivial = (
    // Pure whitespace/newline changes
    (stripped_text == '' and ('\n' in text or '\r' in text or text.isspace())) or
    // Single character additions (except structural chars)
    (len(text) == 1 and text not in '{}[]():;,') or
    // Pure whitespace additions
    (text.isspace() and len(text) <= 4) or
    // Comment-only changes
    (stripped_text.startswith('#') or stripped_text.startswith('//'))
);
```

### Step 3: Improved Cancellation Logic
```jac
// OLD: Basic cancellation
if file_path in self._pending_deep_checks {
    self._pending_deep_checks[file_path].cancel();
    del self._pending_deep_checks[file_path];
}

// NEW: Comprehensive cleanup with version tracking
def _cancel_pending_deep_check(self: JacLangServer, file_path: str) -> None {
    if file_path in self._pending_deep_checks {
        try {
            task = self._pending_deep_checks[file_path];
            if not task.done() {
                task.cancel();
            }
        } except Exception as e {
            self.log_warning(f"'Error cancelling pending deep check: '{e}");
        } finally {
            del self._pending_deep_checks[file_path];
        }
    }
}
```

### Step 4: Single-Shot Debounce Implementation
```jac
// OLD: Recursive rescheduling
async def _debounced_run() -> None {
    await asyncio.sleep(self._debounce_delay_sec);
    if (time.time() - self._last_user_interaction_time) < self._debounce_delay_sec {
        // Reschedule with fresh timer - CREATES NEW TASK
        self.schedule_deep_check(file_path);
        return;
    }
    // ... analysis
}

// NEW: Single extension
async def _optimized_debounced_run() -> None {
    await asyncio.sleep(self._debounce_delay_sec);
    
    time_since_interaction = time.time() - self._last_user_interaction_time;
    if time_since_interaction < self._debounce_delay_sec * 0.8 {
        // Single extension - NO NEW TASK
        await asyncio.sleep(self._debounce_delay_sec * 0.5);
    }
    // ... analysis
}
```

## Validation

### Testing Your Migration
1. **Performance Test**: Type rapidly and verify ~400ms response after stopping
2. **Newline Test**: Press Enter and verify ~200ms syntax highlighting
3. **Memory Test**: Verify task counts don't accumulate during rapid typing
4. **Cancellation Test**: Ensure old analysis stops when new edits arrive

### Expected Behavior Changes
- ✅ **Faster Initial Response**: Syntax highlighting appears sooner
- ✅ **Better Rapid Typing**: Less lag during typing bursts  
- ✅ **Cleaner Memory Usage**: No task accumulation
- ✅ **More Responsive Newlines**: Quick coloring after Enter

### Performance Metrics to Monitor
```jac
// Add logging to verify improvements
self.log_py(f"'PROFILE: Deep check took '{(time.time() - start_time)}' seconds.'");
self.log_py(f"'Pending deep checks: '{len(self._pending_deep_checks)}");
```

## Rollback Plan

If you need to revert to the original behavior:

### Quick Rollback
```jac
// Restore original timing
self._debounce_delay_sec: float = 0.30;           // Back to 300ms
self._min_interval_for_trivial_sec: float = 1.2;  // Back to 1200ms

// Use simple trivial detection
is_trivial = text.strip() == '' and ('\n' in text or '\r' in text or text.isspace());

// Remove version tracking if not needed
// (Keep for stale task prevention)
```

### Full Rollback
1. Restore original `schedule_deep_check` with recursive rescheduling
2. Remove enhanced trivial edit detection  
3. Restore original timing parameters
4. Remove version tracking (not recommended)

## Customization Options

### For Different Use Cases

#### Ultra-Responsive (Gaming/Live Coding)
```jac
self._debounce_delay_sec: float = 0.08;           // 80ms
self._min_interval_for_trivial_sec: float = 0.3;  // 300ms
```

#### Resource Conservative (Low-Power Devices)  
```jac
self._debounce_delay_sec: float = 0.25;           // 250ms
self._min_interval_for_trivial_sec: float = 1.0;  // 1000ms
```

#### Balanced (Recommended Default)
```jac
self._debounce_delay_sec: float = 0.15;           // 150ms  
self._min_interval_for_trivial_sec: float = 0.6;  // 600ms
```

## Support

### Common Issues During Migration
1. **"Still experiencing delays"** → Verify timing parameters updated
2. **"Too many refreshes"** → Increase trivial edit interval
3. **"Memory usage growing"** → Check cancellation logic implementation
4. **"Syntax errors after update"** → Verify all braces/semicolons correct

### Getting Help
- Check the comprehensive documentation: `language_server_optimization.md`
- Use the quick reference: `lsp_optimization_quick_reference.md`  
- Enable performance logging for debugging
- Monitor task counts to verify clean lifecycle management

The optimizations provide significant performance improvements while maintaining backward compatibility. Most users should see immediate benefits with the default configuration.
