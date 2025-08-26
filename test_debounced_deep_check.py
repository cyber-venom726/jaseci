#!/usr/bin/env python3
"""
Test script to verify the debounced deep check implementation.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch


async def test_debounce_behavior():
    """Test that debounced deep check properly delays execution."""
    print("Testing debounced deep check behavior...")
    
    # Mock the JacLangServer
    mock_server = MagicMock()
    mock_server.launch_deep_check = AsyncMock()
    mock_server.log_py = MagicMock()
    
    # Import the debounce decorator
    import sys
    sys.path.append('/home/kuggix/jaseci/jac/jaclang/langserve')
    
    try:
        from utils import debounce
        from jaclang.settings import settings
        
        # Create a debounced function similar to what we implemented
        @debounce(0.3)  # 300ms
        async def test_debounced_function(uri: str):
            mock_server.log_py(f"Debounced function called for {uri}")
            await mock_server.launch_deep_check(uri)
        
        # Test rapid calls - only the last one should execute
        print("Simulating rapid typing...")
        start_time = time.time()
        
        # Simulate 5 rapid changes
        await test_debounced_function("file://test1.jac")
        await asyncio.sleep(0.1)  # 100ms
        await test_debounced_function("file://test1.jac")  
        await asyncio.sleep(0.1)  # 100ms
        await test_debounced_function("file://test1.jac")
        await asyncio.sleep(0.1)  # 100ms
        await test_debounced_function("file://test1.jac")
        await asyncio.sleep(0.1)  # 100ms
        await test_debounced_function("file://test1.jac")
        
        # Wait for debounce to complete
        await asyncio.sleep(0.5)
        
        elapsed = time.time() - start_time
        print(f"Total time elapsed: {elapsed:.2f}s")
        print(f"Deep check was called {mock_server.launch_deep_check.call_count} times")
        
        # Should only be called once due to debouncing
        if mock_server.launch_deep_check.call_count == 1:
            print("✅ SUCCESS: Debouncing worked correctly!")
            print("   - Multiple rapid calls were consolidated into one")
        else:
            print(f"❌ FAILURE: Expected 1 call, got {mock_server.launch_deep_check.call_count}")
            
        # Test different files (should not debounce each other)
        mock_server.launch_deep_check.reset_mock()
        await test_debounced_function("file://test2.jac")
        await test_debounced_function("file://test3.jac")
        await asyncio.sleep(0.5)
        
        print(f"Different files test: {mock_server.launch_deep_check.call_count} calls")
        if mock_server.launch_deep_check.call_count == 2:
            print("✅ SUCCESS: Different files are handled independently!")
        else:
            print(f"❌ Note: Different files behavior - got {mock_server.launch_deep_check.call_count} calls")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure the jac modules are properly set up")
    except Exception as e:
        print(f"❌ Test error: {e}")


if __name__ == "__main__":
    print("=== Debounced Deep Check Test ===")
    asyncio.run(test_debounce_behavior())
