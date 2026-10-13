Auto directives
===============

.. autorandclass:: vsc_doc_fixture.AluTxn
   :members:
   :constraint-show-source: none
   :randclass-summary: none
   :constraint-signature-fields:

.. autocovergroup:: vsc_doc_fixture.AluCov
   :coverpoint-show-bins: false
   :covergroup-summary: none

.. autorandclass:: vsc_doc_fixture.Op

.. autoclass:: vsc_doc_fixture.WideTxn
   :members: w, c_op
   :exclude-members: c_op

Hand-written
------------

.. py:randclass:: Pkt
   :module: handmade

   A packet, described by hand.

   .. py:randfield:: len
      :kind: randc
      :type: u6
      :constrained-by: c_len

   .. py:constraint:: c_len
      :reads: len

      Length is short.

See :py:constraint:`handmade.Pkt.c_len` and :py:randfield:`handmade.Pkt.len`.
