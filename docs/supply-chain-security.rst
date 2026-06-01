Supply chain security
======================

Wiswa generates projects with several supply-chain hardening measures inspired by
`Astral's open source security practices
<https://astral.sh/blog/open-source-security-at-astral>`_.

Pinned actions
--------------

Every generated GitHub Actions workflow pins each action to a full-length commit SHA, resolved from
the action's latest release tag when the project is generated. This is the recommended defence
against a tag or branch being re-pointed at malicious code. Dependabot still proposes updates to
SHA-pinned actions, so the pins stay current. Regenerating the project re-resolves the SHAs.

zizmor
------

GitHub projects gain a `zizmor <https://github.com/zizmorcore/zizmor>`_ pre-commit hook, which
statically analyses workflows for issues such as unpinned actions and impostor commits. Set
``want_zizmor`` to ``false`` to opt out.

Release environment
-------------------

The publish and release-promotion jobs declare a GitHub deployment ``environment`` (``release`` by
default, configurable through ``github.workflows.release_environment``; set it to an empty string to
disable the gate). **Create this environment in the repository settings and add a required-reviewer
protection rule** so another maintainer must approve before a release runs.

Repository configuration
------------------------

When Wiswa configures the GitHub repository (that is, unless ``--skip-remote`` is passed), it also
applies two account-level controls through the API, both enabled by default:

- ``github.sha_pinning_required`` requires that actions are pinned to a full-length commit SHA,
  enforcing the policy server-side to complement the SHA pins in the generated workflows.
- ``github.immutable_oidc_subject`` opts the repository in to the immutable OIDC subject claim
  format, giving trusted publishing a stable, repository-ID-based subject.
