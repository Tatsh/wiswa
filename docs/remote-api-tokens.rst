Remote API tokens
==================

When Wiswa configures the remote (``wiswa`` without ``--skip-remote``), it calls the GitHub or
GitLab API using a **personal access token**. Tokens are read from the environment when supported,
or from the system keyring. Service names include the **repository hostname** so different hosts
(for example GitHub.com, GitHub Enterprise, or self-managed GitLab) keep separate credentials.

Keyring entries use the usual **service name** and **username** fields. The **username** is
normally your OS login name (``whoami``).

GitHub
------

#. Service ``wiswa-github:<hostname>``, username your OS user. The hostname is taken from
   ``repository_uri`` (for example ``github.com`` for ``https://github.com/org/repo``).

Example (hostname ``github.com``, OS user ``alice``):

.. code-block:: shell

   python -m keyring set 'wiswa-github:github.com' alice

GitLab
------

#. **Environment:** ``GITLAB_TOKEN`` (if set, used first).
#. **Preferred:** service ``wiswa-gitlab:<hostname>``, username your OS user (for example
   ``wiswa-gitlab:gitlab.com``).
#. The same service with **username** equal to the hostname is also checked.

Example for ``gitlab.com``:

.. code-block:: shell

   export GITLAB_TOKEN='glpat-...'

   python -m keyring set 'wiswa-gitlab:gitlab.com' "$(whoami)"
