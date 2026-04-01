"""Tests for bot/callback_parsing.py — split_callback_data, parse_int_part."""

from bot.callback_parsing import parse_int_part, split_callback_data


class TestSplitCallbackData:
    def test_empty_string_returns_empty_list(self):
        assert split_callback_data("") == []

    def test_none_returns_empty_list(self):
        assert split_callback_data(None) == []

    def test_simple_split(self):
        assert split_callback_data("crs_0") == ["crs", "0"]

    def test_multi_part(self):
        assert split_callback_data("ann_1_2") == ["ann", "1", "2"]

    def test_maxsplit_respected(self):
        result = split_callback_data("det_0_not_extra", maxsplit=2)
        assert len(result) == 3
        assert result[0] == "det"
        assert result[1] == "0"
        assert result[2] == "not_extra"

    def test_custom_separator(self):
        assert split_callback_data("a:b:c", sep=":") == ["a", "b", "c"]

    def test_no_separator_in_string(self):
        assert split_callback_data("main_menu") == ["main", "menu"]

    def test_single_part(self):
        assert split_callback_data("kontrol") == ["kontrol"]


class TestParseIntPart:
    def test_valid_index(self):
        assert parse_int_part(["crs", "5"], 1) == 5

    def test_zero(self):
        assert parse_int_part(["ann", "0"], 1) == 0

    def test_index_out_of_range(self):
        assert parse_int_part(["crs"], 5) is None

    def test_non_integer_returns_none(self):
        assert parse_int_part(["crs", "abc"], 1) is None

    def test_empty_string_returns_none(self):
        assert parse_int_part(["crs", ""], 1) is None

    def test_negative_number(self):
        assert parse_int_part(["x", "-1"], 1) == -1

    def test_large_number(self):
        assert parse_int_part(["x", "99999"], 1) == 99999

    def test_float_string_returns_none(self):
        assert parse_int_part(["x", "1.5"], 1) is None
