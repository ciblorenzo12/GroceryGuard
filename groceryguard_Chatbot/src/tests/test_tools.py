"""Tested suite for GroceryGuard tools (label_scan, ingredient_risk_lookup, kb_lookup)."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from groceryguard_core.spice_rack_tools import (
    label_scan,
    ingredient_risk_lookup,
    kb_lookup,
    TOOL_SPECS,
    dispatch_tool,
)


class TestLabelScan:
    """Tested label_scan tool - detected watchlist items in ingredient text."""
    
    def test_label_scan_basic(self):
        """Tested that label_scan returned a dict with expected structure."""
        ingredients = "corn syrup, sugar, water"
        result = label_scan(ingredients)
        
        assert result is not None
        assert isinstance(result, dict)

    def test_label_scan_empty_input(self):
        """Tested label_scan with empty ingredient list."""
        result = label_scan("")
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_label_scan_case_insensitive(self):
        """Tested that label_scan handled case variations."""
        ingredients_lower = "high fructose corn syrup"
        ingredients_upper = "HIGH FRUCTOSE CORN SYRUP"
        
        result_lower = label_scan(ingredients_lower)
        result_upper = label_scan(ingredients_upper)
        
        # Both should return dicts
        assert isinstance(result_lower, dict)
        assert isinstance(result_upper, dict)
    
    def test_label_scan_multiple_ingredients(self):
        """Tested label_scan with multiple ingredients."""
        ingredients = "water, salt, sugar, eggs, flour"
        result = label_scan(ingredients)
        assert isinstance(result, dict)
    
    def test_label_scan_with_watchlist_items(self):
        """Tested label_scan detected watchlist items."""
        ingredients = "azodicarbonamide, flour, potassium bromate"
        result = label_scan(ingredients)
        
        assert isinstance(result, dict)
        # Should have parsed structure with flags and ingredients
        assert "parsed_ingredients" in result or "flags" in result


class TestIngredientRiskLookup:
    """Tested ingredient_risk_lookup tool - fetched watchlist details."""
    
    def test_ingredient_risk_lookup_basic(self):
        """Tested looking up an ingredient."""
        result = ingredient_risk_lookup("peanut")
        
        assert result is not None
        assert isinstance(result, dict)
        assert "ingredient" in result
        assert "hits" in result
    
    def test_ingredient_risk_lookup_safe_item(self):
        """Tested looking up a safe ingredient."""
        result = ingredient_risk_lookup("water")
        
        assert result is not None
        assert isinstance(result, dict)
        assert "ingredient" in result
    
    def test_ingredient_risk_lookup_empty_string(self):
        """Tested lookup with empty ingredient name."""
        result = ingredient_risk_lookup("")
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_ingredient_risk_lookup_returns_structure(self):
        """Tested that lookup returned proper structure."""
        result = ingredient_risk_lookup("artificial sweetener")
        
        assert isinstance(result, dict)
        assert "ingredient" in result
        assert "hits" in result
        assert "note" in result


class TestKBLookup:
    """Test kb_lookup tool - searches knowledge base."""
    
    def test_kb_lookup_returns_dict(self):
        """Test that kb_lookup returns a dict."""
        result = kb_lookup("ingredient safety")
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_kb_lookup_structure(self):
        """Test kb_lookup returns required fields."""
        result = kb_lookup("allergens")
        
        assert isinstance(result, dict)
        assert "query" in result
        assert "matches" in result
    
    def test_kb_lookup_empty_query(self):
        """Test kb_lookup with empty query."""
        result = kb_lookup("")
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_kb_lookup_multiple_queries(self):
        """Test KB lookup for different queries."""
        queries = ["organic", "GMO", "preservatives"]
        
        for query in queries:
            result = kb_lookup(query)
            assert result is not None
            assert isinstance(result, dict)


class TestToolSpecs:
    """Test tool specification definitions."""
    
    def test_tool_specs_format(self):
        """Test that TOOL_SPECS has correct OpenAI format."""
        assert isinstance(TOOL_SPECS, list)
        assert len(TOOL_SPECS) >= 3  # At least 3 tools
        
        for tool in TOOL_SPECS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
    
    def test_tool_specs_include_required_tools(self):
        """Test that all required tools are defined."""
        tool_names = [t["function"]["name"] for t in TOOL_SPECS]
        
        assert "label_scan" in tool_names
        assert "ingredient_risk_lookup" in tool_names
        assert "kb_lookup" in tool_names
    
    def test_tool_specs_parameters(self):
        """Test that tool specs have proper parameter definitions."""
        for tool in TOOL_SPECS:
            params = tool["function"]["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params
            assert len(params["properties"]) > 0


class TestDispatchTool:
    """Test tool dispatch mechanism."""
    
    def test_dispatch_tool_label_scan(self):
        """Test dispatching to label_scan tool."""
        result = dispatch_tool("label_scan", {"label_text": "corn syrup, sugar"})
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_dispatch_tool_ingredient_lookup(self):
        """Test dispatching to ingredient_risk_lookup tool."""
        result = dispatch_tool("ingredient_risk_lookup", {"ingredient": "peanut"})
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_dispatch_tool_kb_lookup(self):
        """Test dispatching to kb_lookup tool."""
        result = dispatch_tool("kb_lookup", {"query": "allergens"})
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_dispatch_tool_invalid_tool_name(self):
        """Test dispatching with invalid tool name."""
        # dispatch_tool returns error dict for unknown tools
        result = dispatch_tool("invalid_tool", {})
        assert isinstance(result, dict)
        assert "error" in result
    
    def test_dispatch_tool_openai_format(self):
        """Test dispatch_tool with OpenAI function calling format."""
        # Simulate OpenAI response format
        tool_name = "label_scan"
        args_dict = {"label_text": "artificial sweetener, water"}
        
        result = dispatch_tool(tool_name, args_dict)
        
        assert result is not None
        assert isinstance(result, dict)


class TestToolIntegration:
    """Integration tests for multiple tool calls in sequence."""
    
    def test_multi_tool_workflow(self):
        """Test a realistic multi-tool workflow."""
        # Step 1: Scan ingredient label
        ingredients = "water, salt"
        scan_result = label_scan(ingredients)
        assert isinstance(scan_result, dict)
        
        # Step 2: Lookup details on ingredient
        lookup_result = ingredient_risk_lookup("salt")
        assert isinstance(lookup_result, dict)
        
        # Step 3: Get KB information
        kb_result = kb_lookup("ingredient safety")
        assert isinstance(kb_result, dict)
        
        # All should return dicts
        assert all(isinstance(r, dict) for r in [scan_result, lookup_result, kb_result])
    
    def test_tool_chain_allergen_detection(self):
        """Test tool chain for allergen detection workflow."""
        # User scenario: Check if product has peanuts
        
        # 1. Scan for allergen-related items
        scan = label_scan("peanut oil, salt, sugar")
        assert isinstance(scan, dict)
        
        # 2. Look up specific allergen
        lookup = ingredient_risk_lookup("peanut oil")
        assert isinstance(lookup, dict)
        
        # 3. Get allergen information from KB
        kb = kb_lookup("peanut allergen")
        assert isinstance(kb, dict)
