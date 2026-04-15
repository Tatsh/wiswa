/**
 * @brief Opinionated GitLab project API defaults (project, push rules, approvals, default branch).
 * @file defaults/gitlab.libsonnet
 *
 * Merged in ``defaults.libsonnet`` as ``gitlab``. Override in ``.wiswa.jsonnet`` with
 * ``gitlab+: { project_settings+: { ... }, ... }``.
 */
{
  project_settings: {
    analytics_access_level: 'disabled',
    auto_devops_enabled: 'false',
    build_git_strategy: 'fetch',
    builds_access_level: 'enabled',
    ci_default_git_depth: '20',
    ci_forward_deployment_enabled: 'true',
    ci_job_token_scope_enabled: 'true',
    ci_separated_caches: 'true',
    commit_committer_check: 'true',
    compliance_frameworks: '[]',
    emails_enabled: 'true',
    environments_access_level: 'disabled',
    feature_flags_access_level: 'disabled',
    forking_access_level: 'enabled',
    infrastructure_access_level: 'disabled',
    issues_enabled: 'true',
    keep_latest_artifact: 'true',
    lfs_enabled: 'false',
    member_check: 'true',
    merge_method: 'ff',
    merge_requests_access_level: 'enabled',
    model_experiments_access_level: 'disabled',
    model_registry_access_level: 'disabled',
    monitor_access_level: 'disabled',
    only_allow_merge_if_all_discussions_are_resolved: 'true',
    only_allow_merge_if_pipeline_succeeds: 'true',
    packages_enabled: 'true',
    pages_access_level: 'public',
    pages_unique_domain_enabled: 'true',
    prevent_secrets: 'true',
    printing_merge_request_link_enabled: 'true',
    public_builds: 'true',
    releases_access_level: 'enabled',
    remove_source_branch_after_merge: 'true',
    security_and_compliance_access_level: 'enabled',
    service_desk_enabled: 'false',
    shared_runners_enabled: 'true',
    show_default_award_emojis: 'true',
    snippets_access_level: 'disabled',
    squash_option: 'default_off',
    warn_about_potentially_unwanted_characters: 'true',
    wiki_access_level: 'disabled',
  },
  push_rules: {
    prevent_secrets: 'true',
  },
  project_approvals: {
    approvals_before_merge: 1,
    merge_requests_author_approval: 'false',
    reset_approvals_on_push: 'true',
  },
  default_branch_protection: {
    allow_force_push: 'true',
    code_owner_approval_required: 'false',
  },
}
