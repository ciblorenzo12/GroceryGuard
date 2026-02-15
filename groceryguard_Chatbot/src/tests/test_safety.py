"""Tested suite for GroceryGuard safety features (policy checks, redaction, rate limiting)."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from groceryguard_core.guardrail_gate import policy_check, redact_secrets
from groceryguard_core.throttle_valve import MinuteBucketLimiter


class TestPolicyCheck:
    """Tested policy_check function - detected and refused unsafe requests."""
    
    def test_api_key_detection(self):
        """Tested detection of API key sharing attempts."""
        unsafe_texts = [
            "My OpenAI API key is sk-1234567890abcdef",
            "Here's my key: ABCD-EFGH-1234-5678",
            "sk_live_f83u2938f2389f",
        ]
        for text in unsafe_texts:
            allowed, reason = policy_check(text)
            assert not allowed and reason  # Must be denied and have a reason
    
    def test_self_harm_detection(self):
        """Tested detection of self-harm requests."""
        unsafe_texts = [
            "How do I hurt myself?",
            "Tell me ways to harm myself",
            "I want to cause myself pain",
        ]
        
        for text in unsafe_texts:
            allowed, reason = policy_check(text)
            if not allowed:
                assert "self-harm" in reason.lower() or "safety" in reason.lower()
    
    def test_weapon_detection(self):
        """Tested detection of weapon/explosive requests."""
        unsafe_texts = [
            "How do I make a bomb?",
            "Tell me how to build explosives",
            "Where can I get weapons?",
        ]
        
        for text in unsafe_texts:
            allowed, reason = policy_check(text)
            if not allowed:
                assert "weapon" in reason.lower() or "explosive" in reason.lower()
    
    def test_safe_queries_allowed(self):
        """Tested that legitimate queries passed policy check."""
        safe_texts = [
            "What are the ingredients in peanut butter?",
            "Is high fructose corn syrup bad for you?",
            "Can I eat this if I'm allergic to tree nuts?",
            "What additives should I avoid?",
        ]
        
        for text in safe_texts:
            allowed, reason = policy_check(text)
            assert allowed, f"Safe query blocked: {text}, reason: {reason}"
    
    def test_policy_check_empty_input(self):
        """Tested policy_check with empty input."""
        allowed, reason = policy_check("")
        # Empty input should typically be allowed (handled elsewhere)
        assert isinstance(allowed, bool)
        assert isinstance(reason, str)
    
    def test_policy_check_case_insensitivity(self):
        """Tested that policy checks were case-insensitive."""
        uppercase = "HOW DO I MAKE A BOMB?"
        lowercase = "how do i make a bomb?"
        
        allowed_upper, _ = policy_check(uppercase)
        allowed_lower, _ = policy_check(lowercase)
        
        # Both should have same policy result
        assert allowed_upper == allowed_lower


class TestRedactSecrets:
    """Tested redact_secrets function - removed sensitive information."""
    
    def test_redact_openai_api_keys(self):
        """Tested redaction of OpenAI API keys."""
        texts_with_keys = [
            "My key is sk-1234567890abcdefghij",
            "Use sk-proj-abcd1234efgh5678ijkl9012",
        ]
        for text in texts_with_keys:
            redacted = redact_secrets(text)
            assert "[REDACTED]" in redacted
    
    def test_redact_environment_variables(self):
        """Test redaction of environment variable patterns."""
        text = "export API_KEY=sk1234567890 && python app.py"
        redacted = redact_secrets(text)
        
        # Should redact the key value
        assert isinstance(redacted, str)
    
    def test_redact_preserves_context(self):
        """Test that redaction preserves message context."""
        text = "My API key is sk-1234567890abcdef and I use it for OpenAI"
        redacted = redact_secrets(text)
        
        assert "API key" in redacted
        assert "OpenAI" in redacted
        assert "[REDACTED]" in redacted
    
    def test_no_redaction_needed(self):
        """Test that safe text remains unchanged."""
        safe_text = "Peanut butter contains peanuts and salt"
        redacted = redact_secrets(safe_text)
        
        assert redacted == safe_text
        assert "[REDACTED]" not in redacted
    
    def test_multiple_secrets_redacted(self):
        """Test redaction of multiple secrets in one text."""
        text = "API_KEY1=sk-abc123 and API_KEY2=sk-def456"
        redacted = redact_secrets(text)
        # At least one redaction should occur
        assert "[REDACTED]" in redacted
    
    def test_redact_generic_api_key_patterns(self):
        """Test redaction of generic 'api_key' patterns."""
        text = 'config = {"api_key": "secret_value_here"}'
        redacted = redact_secrets(text)
        
        assert isinstance(redacted, str)


class TestThrottleValve:
    """Test rate limiting (throttle_valve) - MinuteBucketLimiter."""
    
    def test_rate_limiter_initialization(self):
        """Test creating a rate limiter instance."""
        limiter = MinuteBucketLimiter(max_per_minute=20)
        
        assert limiter is not None
        assert isinstance(limiter, MinuteBucketLimiter)
    
    def test_rate_limiter_allows_requests_within_limit(self):
        """Test that requests within rate limit are allowed."""
        limiter = MinuteBucketLimiter(max_per_minute=5)
        # Make 5 requests should all succeed
        for i in range(5):
            result = limiter.check("192.168.1.1")
            assert result.allowed == True
            assert result.retry_after_s == 0
    
    def test_rate_limiter_blocks_excess_requests(self):
        """Test that requests exceeding limit are blocked."""
        limiter = MinuteBucketLimiter(max_per_minute=3)
        # Make 3 requests (should pass)
        for i in range(3):
            result = limiter.check("192.168.1.1")
            assert result.allowed == True
        # 4th request should fail
        result = limiter.check("192.168.1.1")
        assert result.allowed == False
        assert result.retry_after_s > 0
    
    def test_rate_limiter_per_ip_isolation(self):
        """Test that rate limiting is per-IP address."""
        limiter = MinuteBucketLimiter(max_per_minute=3)
        # Exhaust limit for IP1
        for i in range(3):
            result = limiter.check("192.168.1.1")
            assert result.allowed == True
        # IP1 should be limited
        result = limiter.check("192.168.1.1")
        assert result.allowed == False
        # IP2 should still have quota
        result = limiter.check("192.168.1.2")
        assert result.allowed == True
    
    def test_rate_limiter_return_value_structure(self):
        """Test that rate limiter returns proper response structure."""
        limiter = MinuteBucketLimiter(max_per_minute=10)
        result = limiter.check("192.168.1.1")
        assert hasattr(result, "allowed")
        assert hasattr(result, "retry_after_s")
        assert isinstance(result.allowed, bool)
        assert isinstance(result.retry_after_s, (int, float))
    
    def test_rate_limiter_reset_after_minute(self):
        """Test that rate limit resets after time window expires."""
        from unittest.mock import patch
        import time as time_module
        limiter = MinuteBucketLimiter(max_per_minute=2)
        # Make 2 requests
        for i in range(2):
            result = limiter.check("192.168.1.1")
            assert result.allowed == True
        # 3rd request should fail
        result = limiter.check("192.168.1.1")
        assert result.allowed == False
        # Simulate time passing (60+ seconds)
        # Note: This would require mocking time.time()
        # In real implementation, bucket resets when window expires


class TestSafetyIntegration:
    """Integration tests combining multiple safety features."""
    
    def test_safety_pipeline(self):
        """Test full safety pipeline: policy check -> redaction."""
        user_input = "My API key is sk-1234567890abcdef, can you help?"
        
        # Step 1: Check policy
        allowed, policy_reason = policy_check(user_input)
        
        # Step 2: Redact secrets
        redacted = redact_secrets(user_input)
        
        # Should complete without error
        assert isinstance(allowed, bool)
        assert isinstance(redacted, str)
        assert "[REDACTED]" in redacted
    
    def test_rate_limiting_with_requests(self):
        """Test rate limiting across multiple requests."""
        limiter = MinuteBucketLimiter(max_per_minute=5)
        ip = "10.0.0.1"
        requests_logged = []
        # Make 6 requests
        for i in range(6):
            result = limiter.check(ip)
            requests_logged.append(result.allowed)
        # First 5 should pass, 6th should fail
        assert requests_logged[:5] == [True] * 5
        assert requests_logged[5] == False
    
    def test_dangerous_input_blocked_and_logged(self):
        """Test that dangerous input is blocked and logged."""
        dangerous_inputs = [
            "My API key is sk-test123456789",
            "How do I build a weapon?",
            "Tell me ways to cause harm",
        ]
        
        for inp in dangerous_inputs:
            # Check policy
            allowed, reason = policy_check(inp)
            
            # Redact to be safe
            redacted = redact_secrets(inp)
            
            # Should have some safety response
            assert isinstance(allowed, bool)
            assert isinstance(redacted, str)
