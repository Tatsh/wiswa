/**
 * @file yapf.libsonnet
 * @brief Default configuration for YAPF code formatter.
 * @namespace yapf
 */
{
  /** @brief If true, aligns the closing bracket with the visual indent of the line containing the opening bracket. */
  align_closing_bracket_with_visual_indent: true,
  /** @brief If true, allows dictionary keys to be split across multiple lines. */
  allow_multiline_dictionary_keys: false,
  /** @brief If true, allows lambda functions to be split across multiple lines. */
  allow_multiline_lambdas: false,
  /** @brief If true, allows splitting before the value in a dictionary entry. */
  allow_split_before_dict_value: true,
  /** @brief If true, inserts a blank line before a class docstring. */
  blank_line_before_class_docstring: false,
  /** @brief If true, inserts a blank line before the module docstring. */
  blank_line_before_module_docstring: false,
  /** @brief If true, inserts a blank line before a nested class or function definition. */
  blank_line_before_nested_class_or_def: false,
  /** @brief Number of blank lines surrounding top-level function and class definitions. */
  blank_lines_around_top_level_definition: 2,
  /** @brief If true, consecutive closing brackets are placed on the same line. */
  coalesce_brackets: true,
  /** @brief The maximum number of characters allowed on a single line. */
  column_limit: 100,
  /** @brief The style for continuation alignment. Valid values are 'SPACE', 'FIXED', and 'VALIGN-RIGHT'. */
  continuation_align_style: 'SPACE',
  /** @brief The number of columns to indent continuation lines. */
  continuation_indent_width: 4,
  /** @brief If true, closing brackets are de-dented to match the opening bracket's indentation. */
  dedent_closing_brackets: false,
  /** @brief If true, disables the heuristic that places each element on a separate line when a trailing comma is present. */
  disable_ending_comma_heuristic: false,
  /** @brief If true, places each dictionary entry on a separate line. */
  each_dict_entry_on_separate_line: true,
  /** @brief If true, indents dictionary values when they are on a separate line from the key. */
  indent_dictionary_value: true,
  /** @brief The number of columns to use for indentation. */
  indent_width: 4,
  /** @brief If true, joins short lines into one line where possible. */
  join_multiple_lines: true,
  /** @brief If true, removes spaces around selected binary operators (e.g., multiplication and power). */
  no_spaces_around_selected_binary_operators: false,
  /** @brief If true, inserts a space between a trailing comma and the closing bracket. */
  space_between_ending_comma_and_closing_bracket: false,
  /** @brief If true, inserts spaces around the assignment operator for default or keyword arguments. */
  spaces_around_default_or_named_assign: false,
  /** @brief If true, inserts spaces around the power operator (**). */
  spaces_around_power_operator: true,
  /** @brief The number of spaces required before a trailing comment. */
  spaces_before_comment: 2,
  /** @brief If true, splits all comma-separated values onto separate lines regardless of line length. */
  split_all_comma_separated_values: false,
  /** @brief If true, splits arguments onto separate lines when the list is terminated with a comma. */
  split_arguments_when_comma_terminated: false,
  /** @brief If true, prefers splitting before a bitwise operator. */
  split_before_bitwise_operator: true,
  /** @brief If true, splits before the closing bracket if a list or function call does not fit on a single line. */
  split_before_closing_bracket: true,
  /** @brief If true, splits before dictionary, set, or generator expressions. */
  split_before_dict_set_generator: true,
  /** @brief If true, splits before the dot (.) operator in chained calls. */
  split_before_dot: false,
  /** @brief If true, splits before the first expression after an opening parenthesis. */
  split_before_expression_after_opening_paren: false,
  /** @brief If true, splits before the first argument to a function call if all arguments cannot fit on one line. */
  split_before_first_argument: false,
  /** @brief If true, prefers splitting before a logical operator (and, or). */
  split_before_logical_operator: true,
  /** @brief If true, splits before named assigns (keyword arguments). */
  split_before_named_assigns: true,
  /** @brief If true, splits complex comprehensions onto separate lines. */
  split_complex_comprehension: false,
  /** @brief The penalty for splitting after an opening bracket. */
  split_penalty_after_opening_bracket: 30,
  /** @brief The penalty for splitting after a unary operator. */
  split_penalty_after_unary_operator: 10000,
  /** @brief The penalty for splitting before an if expression. */
  split_penalty_before_if_expr: 0,
  /** @brief The penalty for splitting around a bitwise operator. */
  split_penalty_bitwise_operator: 300,
  /** @brief The penalty for splitting a comprehension. */
  split_penalty_comprehension: 80,
  /** @brief The penalty for each character that exceeds the column limit. */
  split_penalty_excess_character: 7000,
  /** @brief The penalty for each additional line split introduced. */
  split_penalty_for_added_line_split: 30,
  /** @brief The penalty for splitting import names. */
  split_penalty_import_names: 0,
  /** @brief The penalty for splitting around a logical operator. */
  split_penalty_logical_operator: 300,
  /** @brief If true, uses tabs for indentation instead of spaces. */
  use_tabs: false,
}
