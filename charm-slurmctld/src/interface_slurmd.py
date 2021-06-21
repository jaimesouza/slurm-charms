#!/usr/bin/env python3
"""Interface slurmd."""
import copy
import json
import logging

from ops.framework import (
    EventBase, EventSource, Object, ObjectEvents, StoredState
)


logger = logging.getLogger()


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdBrokenEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdInventoryEvents(ObjectEvents):
    """SlurmClusterProviderRelationEvents."""

    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_unavailable = EventSource(SlurmdBrokenEvent)


class Slurmd(Object):
    """Slurmd inventory interface."""

    on = SlurmdInventoryEvents()
    _state = StoredState()

    def __init__(self, charm, relation_name):
        """Set self._relation_name and self.charm."""
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        self.framework.observe(
            self._charm.on[self._relation_name].relation_created,
            self._on_relation_created,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_departed,
            self._on_relation_changed,
        )
        self.framework.observe(
            self._charm.on[self._relation_name].relation_broken,
            self._on_relation_broken,
        )

    def _on_relation_created(self, event):
        """Set our data on the relation."""
        # Check that slurm has been installed so that we know the munge key is
        # available. Defer if slurm has not been installed yet.
        if not self._charm.is_slurm_installed():
            event.defer()
            return

        # make sure slurmdbd started before sending signal to slurmd
        if not self._charm.slurmdbd_info:
            event.defer()
            return

        # Get the munge_key from set it to the app data on the relation to be
        # retrieved on the other side by slurmdbd.
        app_relation_data = event.relation.data[self.model.app]
        app_relation_data["munge_key"] = self._charm.get_munge_key()

        # send the hostname and port to enable configless mode
        app_relation_data["slurmctld_host"] = self._charm.hostname
        app_relation_data["slurmctld_port"] = self._charm.port

    def _on_relation_changed(self, event):
        """Emit slurmd available event."""
        if event.relation.data[event.app].get("partition_info"):
            self._charm.set_slurmd_available(True)
            self.on.slurmd_available.emit()
        else:
            event.defer()

    def _on_relation_broken(self, event):
        """Clear the munge key and emit the event if the relation is broken."""
        if self.framework.model.unit.is_leader():
            event.relation.data[self.model.app]["munge_key"] = ""
        self._charm.set_slurmd_available(False)
        self.on.slurmd_unavailable.emit()

    @property
    def _num_relations(self):
        """Return the number of relations."""
        return len(self._charm.framework.model.relations["slurmd"])

    @property
    def is_joined(self):
        """Return True if self._relation is not None."""
        return self._num_relations > 0

    def get_slurmd_info(self):
        """Return the node info for units of applications on the relation."""
        partitions = list()
        relations = self.framework.model.relations["slurmd"]

        for relation in relations:
            inventory = list()

            app = relation.app
            units = relation.units

            partition_info = json.loads(relation.data[app]["partition_info"])

            for unit in units:
                inv = relation.data[unit].get("inventory")
                if inv:
                    inventory.append(json.loads(inv))

            partition_info["inventory"] = inventory.copy()
            partitions.append(partition_info)

        return ensure_unique_partitions(partitions)


def ensure_unique_partitions(partitions):
    """Return a list of unique partitions."""
    # Ensure we have partitions with unique inventory only
    #
    # 1) Create a temp copy of the partitions list and iterate
    # over it.
    #
    # 2) On each pass create a temp copy of the partition itself.
    #
    # 3) Get the inventory from the temp partition and iterate over it to
    # ensure we have unique entries.
    #
    # 4) Add the unique inventory back to the temp partition and
    # subsequently add the temp partition back to the original partitions
    # list.
    #
    # 5) Return the list of partitions with unique inventory.

    partitions_tmp = copy.deepcopy(partitions)
    for partition in partitions_tmp:

        partition_tmp = copy.deepcopy(partition)
        partitions.remove(partition)

        inventory = partition_tmp["inventory"]

        unique_inventory = list(
            {node["node_name"]: node for node in inventory}.values()
        )

        partition_tmp["inventory"] = unique_inventory
        partitions.append(partition_tmp)

    return partitions
