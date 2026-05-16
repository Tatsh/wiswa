function(dialect) {
  core: {
    dialect: 'postgres',
    large_file_skip_byte_limit: 0,
    max_line_length: 100,
    output_line_length: 100,
    processes: -1,
    templater: 'placeholder',
  },
  indentation: {
    indented_ctes: true,
    indented_joins: true,
    tab_space_size: 2,
  },
  rules: {
    allow_scalar: false,
    capitalisation_policy: 'upper',
    extended_capitalisation_policy: 'upper',
    group_by_and_order_by_style: 'explicit',
    preferred_type_casting_style: 'cast',
    quoted_identifiers_policy: 'all',
    select_clause_trailing_comma: 'forbid',
    unquoted_identifiers_policy: 'all',
    aliasing: {
      expression: {
        allow_scalar: true,
      },
    },
    capitalisation: {
      functions: {
        capitalisation_policy: 'upper',
        extended_capitalisation_policy: 'upper',
      },
    } + (
      if dialect == 'snowflake' then {
        identifiers: {
          capitalisation_policy: 'upper',
          extended_capitalisation_policy: 'upper',
        },
      } else {}
    ) + {
      keywords: {
        capitalisation_policy: 'upper',
        extended_capitalisation_policy: 'upper',
      },
      literals: {
        capitalisation_policy: 'upper',
        extended_capitalisation_policy: 'upper',
      },
      types: {
        capitalisation_policy: 'upper',
        extended_capitalisation_policy: 'upper',
      },
    },
    convention: {
      not_equal: {
        preferred_not_equal_style: 'c_style',
      },
    },
  },
  templater: {
    placeholder: {
      param_style: 'pyformat',
    },
  },
}
