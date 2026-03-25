wiswa
=====

.. include:: badges.rst

Commands
--------

.. click:: wiswa.main:main
  :prog: wiswa
  :nested: full

MCP Server
----------

Wiswa includes an MCP server (``wiswa-mcp``) that exposes settings discovery tools for AI
assistants.

Claude Code
^^^^^^^^^^^

.. code-block:: shell

   claude mcp add wiswa-mcp -- wiswa-mcp

Cursor
^^^^^^

Add to ``.cursor/mcp.json``:

.. code-block:: json

   {
     "mcpServers": {
       "wiswa-mcp": {
         "command": "wiswa-mcp"
       }
     }
   }

GitHub Copilot CLI
^^^^^^^^^^^^^^^^^^

Add to ``.github/copilot/mcp.json``:

.. code-block:: json

   {
     "mcpServers": {
       "wiswa-mcp": {
         "command": "wiswa-mcp"
       }
     }
   }

.. only:: html

   Library
   -------
   .. automodule:: wiswa
      :members:

   .. automodule:: wiswa.constants
      :members:

   .. automodule:: wiswa.extensions
      :members:

   .. automodule:: wiswa.typing
      :members:

   .. automodule:: wiswa.utils
      :members:

   Indices and tables
   ==================

   * :ref:`genindex`
   * :ref:`modindex`
