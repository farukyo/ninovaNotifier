"""
Tests for bot/keyboards.py module.
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBuildMainKeyboard:
    """Tests for build_main_keyboard function."""
    
    def test_returns_keyboard_markup(self):
        """Test that function returns ReplyKeyboardMarkup."""
        from bot.keyboards import build_main_keyboard
        from telebot import types
        
        result = build_main_keyboard()
        assert isinstance(result, types.ReplyKeyboardMarkup)
    
    def test_keyboard_is_resizable(self):
        """Test that keyboard is resizable."""
        from bot.keyboards import build_main_keyboard
        
        result = build_main_keyboard()
        assert result.resize_keyboard == True
    
    def test_keyboard_has_multiple_rows(self):
        """Test that keyboard has multiple rows."""
        from bot.keyboards import build_main_keyboard
        
        result = build_main_keyboard()
        assert len(result.keyboard) >= 3
    
    def test_keyboard_contains_expected_buttons(self):
        """Test that keyboard contains expected button labels."""
        from bot.keyboards import build_main_keyboard
        
        result = build_main_keyboard()
        
        # Flatten all button texts
        all_texts = []
        for row in result.keyboard:
            for button in row:
                all_texts.append(button.text if hasattr(button, 'text') else str(button))
        
        # Check for key buttons
        assert any("Notlar" in str(t) for t in all_texts)
        assert any("Ödevler" in str(t) for t in all_texts)
        assert any("Dersler" in str(t) for t in all_texts)
        assert any("Yardım" in str(t) for t in all_texts)


class TestBuildManualMenu:
    """Tests for build_manual_menu function."""
    
    def test_returns_inline_keyboard(self):
        """Test that function returns InlineKeyboardMarkup."""
        from bot.keyboards import build_manual_menu
        from telebot import types
        
        result = build_manual_menu()
        assert isinstance(result, types.InlineKeyboardMarkup)
    
    def test_has_add_button(self):
        """Test that menu has add course button."""
        from bot.keyboards import build_manual_menu
        
        result = build_manual_menu()
        
        # Check inline keyboard buttons
        all_callbacks = []
        for row in result.keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert "manual_add" in all_callbacks
    
    def test_has_delete_button(self):
        """Test that menu has delete course button."""
        from bot.keyboards import build_manual_menu
        
        result = build_manual_menu()
        
        all_callbacks = []
        for row in result.keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert "manual_delete" in all_callbacks
    
    def test_has_list_button(self):
        """Test that menu has list courses button."""
        from bot.keyboards import build_manual_menu
        
        result = build_manual_menu()
        
        all_callbacks = []
        for row in result.keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert "manual_list" in all_callbacks


class TestBuildCancelKeyboard:
    """Tests for build_cancel_keyboard function."""
    
    def test_returns_keyboard_markup(self):
        """Test that function returns ReplyKeyboardMarkup."""
        from bot.keyboards import build_cancel_keyboard
        from telebot import types
        
        result = build_cancel_keyboard()
        assert isinstance(result, types.ReplyKeyboardMarkup)
    
    def test_keyboard_is_resizable(self):
        """Test that keyboard is resizable."""
        from bot.keyboards import build_cancel_keyboard
        
        result = build_cancel_keyboard()
        assert result.resize_keyboard == True
    
    def test_keyboard_is_one_time(self):
        """Test that keyboard is one-time."""
        from bot.keyboards import build_cancel_keyboard
        
        result = build_cancel_keyboard()
        assert result.one_time_keyboard == True
    
    def test_has_cancel_button(self):
        """Test that keyboard has cancel button."""
        from bot.keyboards import build_cancel_keyboard
        
        result = build_cancel_keyboard()
        
        # Check for cancel button
        all_texts = []
        for row in result.keyboard:
            for button in row:
                all_texts.append(button.text if hasattr(button, 'text') else str(button))
        
        assert any("İptal" in str(t) for t in all_texts)
