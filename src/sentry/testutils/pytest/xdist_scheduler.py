"""Deterministic xdist scheduler for Sentry.

Assigns test files to workers via round-robin on the sorted list of file
scopes, then sends each worker its full workload upfront.  Within each file,
tests run in collection order.  This guarantees:

1. Every run with the same collection produces identical worker assignments.
2. Tests within a file always execute in the same order.
3. No dynamic load-balancing or shuffling — critical for test suites with
   ordering-sensitive fixtures or ClickHouse isolation assumptions.
"""

from __future__ import annotations

from collections import OrderedDict

from _pytest.runner import CollectReport
from xdist.remote import Producer
from xdist.report import report_collection_diff
from xdist.workermanage import parse_spec_config


class DeterministicScheduling:
    """Distribute tests deterministically: round-robin by file, all work sent upfront."""

    def __init__(self, config, log=None):
        self.numnodes = len(parse_spec_config(config))
        self.collection: list[str] | None = None
        self.registered_collections: OrderedDict = OrderedDict()
        self.assigned_work: OrderedDict = OrderedDict()
        # Track pending count per node for tests_finished / has_pending.
        self._pending: dict = {}
        self.config = config

        if log is None:
            self.log = Producer("deterministicsched")
        else:
            self.log = log.deterministicsched

    # -- properties required by DSession ------------------------------------

    @property
    def nodes(self):
        return list(self.assigned_work.keys())

    @property
    def collection_is_completed(self):
        return len(self.registered_collections) >= self.numnodes

    @property
    def tests_finished(self):
        if not self.collection_is_completed:
            return False
        return all(p == 0 for p in self._pending.values())

    @property
    def has_pending(self):
        return any(p > 0 for p in self._pending.values())

    # -- node management ----------------------------------------------------

    def add_node(self, node):
        assert node not in self.assigned_work
        self.assigned_work[node] = OrderedDict()
        self._pending[node] = 0

    def remove_node(self, node):
        workload = self.assigned_work.pop(node, OrderedDict())
        self._pending.pop(node, None)

        # Find the crashing test if any pending work remains.
        for work_unit in workload.values():
            for nodeid, completed in work_unit.items():
                if not completed:
                    return nodeid
        return None

    def add_node_collection(self, node, collection):
        assert node in self.assigned_work

        if self.collection_is_completed:
            assert self.collection
            if collection != self.collection:
                other_node = next(iter(self.registered_collections.keys()))
                msg = report_collection_diff(
                    self.collection, collection, other_node.gateway.id, node.gateway.id
                )
                self.log(msg)
                return

        self.registered_collections[node] = list(collection)

    # -- test tracking ------------------------------------------------------

    def mark_test_complete(self, node, item_index, duration=0):
        nodeid = self.registered_collections[node][item_index]
        scope = self._split_scope(nodeid)
        self.assigned_work[node][scope][nodeid] = True
        self._pending[node] -= 1

    def mark_test_pending(self, item):
        raise NotImplementedError()

    # -- scheduling ---------------------------------------------------------

    def schedule(self):
        assert self.collection_is_completed

        # If already distributed, nothing to do (deterministic = no reschedule).
        if self.collection is not None:
            return

        if not self._check_nodes_have_same_collection():
            self.log("**Different tests collected, aborting run**")
            return

        self.collection = list(next(iter(self.registered_collections.values())))
        if not self.collection:
            return

        # Group tests by file scope, preserving collection order.
        scopes: OrderedDict[str, OrderedDict[str, bool]] = OrderedDict()
        for nodeid in self.collection:
            scope = self._split_scope(nodeid)
            scopes.setdefault(scope, OrderedDict())[nodeid] = False

        scope_list = list(scopes.items())
        active_nodes = list(self.nodes)

        # Shut down excess nodes.
        while len(active_nodes) > len(scope_list):
            excess = active_nodes.pop()
            self.assigned_work.pop(excess, None)
            self._pending.pop(excess, None)
            excess.shutdown()

        # Round-robin assignment: file i goes to worker i % n.
        node_indices: dict = {node: [] for node in active_nodes}
        for i, (scope, work_unit) in enumerate(scope_list):
            node = active_nodes[i % len(active_nodes)]
            self.assigned_work[node][scope] = work_unit
            self._pending[node] = self._pending.get(node, 0) + len(work_unit)

            worker_collection = self.registered_collections[node]
            for nodeid in work_unit:
                node_indices[node].append(worker_collection.index(nodeid))

        # Send all work to each node then immediately tell it to shut down.
        # The xdist worker only runs its last queued test upon receiving
        # the "shutdown" command (see xdist/remote.py pytest_runtestloop).
        for node, indices in node_indices.items():
            if indices:
                node.send_runtest_some(indices)
            node.shutdown()

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _split_scope(nodeid: str) -> str:
        """Group by file path (everything before the first ::)."""
        return nodeid.split("::", 1)[0]

    def _check_nodes_have_same_collection(self):
        node_collection_items = list(self.registered_collections.items())
        first_node, col = node_collection_items[0]
        same_collection = True

        for node, collection in node_collection_items[1:]:
            msg = report_collection_diff(col, collection, first_node.gateway.id, node.gateway.id)
            if not msg:
                continue

            same_collection = False
            self.log(msg)

            if self.config is not None:
                rep = CollectReport(node.gateway.id, "failed", longrepr=msg, result=[])
                self.config.hook.pytest_collectreport(report=rep)

        return same_collection
