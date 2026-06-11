# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Created on Jun 9, 2026
#
# Bidirectional FieldModel <-> dv-solve var_id mapping (design §4.4, plan P1-1).


class VarIdMap(object):
    """Maps each solver variable (a ``FieldScalarModel``) to a monotonic
    ``uint32`` var_id and back. Scoped to a single solve (one per RandSet);
    ids start at 0 and increase as fields are added.

    A field is a *variable* iff it has been registered here via ``add`` /
    ``id_of``. Fields not present are treated as constants by the translator.
    """

    def __init__(self):
        self._field_to_id = {}
        self._id_to_field = {}
        self._next_id = 0

    def add(self, field) -> int:
        """Register ``field`` (idempotent) and return its var_id."""
        vid = self._field_to_id.get(field)
        if vid is None:
            vid = self._next_id
            self._next_id += 1
            self._field_to_id[field] = vid
            self._id_to_field[vid] = field
        return vid

    def alloc_aux(self) -> int:
        """Allocate a fresh var_id not bound to any field (a flattening
        auxiliary). It shares the monotonic counter with field ids so it never
        collides; it has no field, so it is skipped on value read-back."""
        vid = self._next_id
        self._next_id += 1
        return vid

    def has(self, field) -> bool:
        return field in self._field_to_id

    def id_of(self, field) -> int:
        """Return the var_id for an already-registered field."""
        return self._field_to_id[field]

    def field_of(self, vid: int):
        """Return the field for a var_id."""
        return self._id_to_field[vid]

    def fields(self):
        """Iterate (field, var_id) pairs in registration order."""
        return ((self._id_to_field[i], i) for i in range(self._next_id))

    def __len__(self):
        return self._next_id
