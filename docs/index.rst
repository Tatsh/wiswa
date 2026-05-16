wiswa
=====

Installation
------------

We recommend a **global** install so ``wiswa`` is on your ``PATH`` from any
working directory:

.. code-block:: shell

   uv tool install wiswa

Or with pipx:

.. code-block:: shell

   pipx install wiswa

If you prefer not to install globally, add Wiswa as a **development
dependency** of your project—for example ``uv add --group dev wiswa``, or list
``wiswa`` under ``dependency-groups.dev`` in ``pyproject.toml`` and install
inside the project virtual environment with your usual workflow.

.. only:: html

   .. include:: badges.rst

.. only:: html

   .. image:: ../demo.gif
      :alt: demo

.. click:: wiswa.tool.main:main
   :prog: wiswa
   :nested: full

.. toctree::
   :hidden:

   remote-api-tokens
   binary-signing

.. only:: html

   .. toctree::
      :hidden:

      library/index


   Indices and tables
   ==================

   * :ref:`genindex`
   * :ref:`modindex`
