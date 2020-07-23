# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Library to generate, maintain, and read static subordinate pool maps."""

import collections
import itertools
import json
import os


# Used to store a unique subordinate class. Consists of a name and an optional
# subclass.
SubordinateClass = collections.namedtuple('SubordinateClass',
    ('name', 'subtype'))

# Used to store a full subordinate configuration. Each subordinate class maps to a single
# subordinate configuration.
SubordinateClassConfig = collections.namedtuple('SubordinateClassConfig',
    ('cls', 'exclusive', 'pools', 'count'))

# Used to store associations between subordinate class and subordinates. Also used to
# store persistent state.
SubordinateState = collections.namedtuple('SubordinateState',
    ('class_map', 'unallocated'))

# Used to store a subordinate map entry (see SubordinateAllocator.GetSubordinateMap())
SubordinateMap = collections.namedtuple('SubordinateMap',
    ('entries', 'unallocated'))

# Used to store a subordinate map entry (see SubordinateAllocator.GetSubordinateMap())
SubordinateMapEntry = collections.namedtuple('SubordinateMapEntry',
    ('classes', 'keys'))


class SubordinateAllocator(object):
  """A subordinate pool management object.

  Pools:
  Individual subordinate machines are added to named Pools. A subordinate cannot be a member
  of more than one pool.

  Classes:
  A Class is a named allocation specification. When allocation is performed,
  the allocator maps Clases to Subordinates. Therefore, a Class is the unit at which
  allocation is performed.

  Classes may optionally include a subtype string to help disambiguate them;
  for all practical purposes the subtype is just part of the name.

  The primary allocation function, '_GetSubordinateClassMap', deterministically
  associates Classes with sets of subordinates from the registered Pools according
  to their registered specification.

  Keys:
  Keys are a generalization of a builder name, representing a specific entity
  that requires subordinate allocation. While key names need not correspond to
  builder names, it is expected that they largely will.

  In order to be assigned, Keys gain Class membership via 'Join()'. A key may
  join multiple classes, and will be assigned the superset of subordinates that those
  classes were assigned.

  State:
  The Allocator may optionally save and load its class allocation state to an
  external JSON file. This can be used to enforce class-to-subordinate mapping
  consistency (i.e., builder affinity).

  When a new allocation is performed, the SubordinateAllocator's State is updated, and
  subsequent operations will prefer the previous layout.
  """

  # The default path to load/save state to, if none is specified.
  DEFAULT_STATE_PATH = 'subordinate_pool.json'

  def __init__(self, state_path=None, list_unallocated=False):
    """Initializes a new subordinate pool instance.

    Args:
      state_path (str): The path (relative or absolute) of the allocation
          save-state JSON file. If None, DEFAULT_STATE_PATH will be used.
      list_unallocated (bool): Include an entry listing unallocated subordinates.
          This entry will be ignored for operations, but can be useful when
          generating expectations.
    """
    self._state_path = state_path
    self._list_unallocated = list_unallocated

    self._state = None
    self._pools = {}
    self._classes = {}
    self._membership = {}
    self._all_subordinates = {}

  @property
  def state_path(self):
    return self._state_path or self.DEFAULT_STATE_PATH

  def LoadStateDict(self, state_class_map=None):
    """Loads previous allocation state from a state dictionary.

    The state dictionary is structured:
      <class-name>: {
        <class-subtype>: [
          <subordinate>
          ...
        ],
        ...
      }

    Args:
      state_class_map (dict): A state class map dictionary. If None or empty,
          the current state will be cleared.
    """
    if not state_class_map:
      self._state = None
      return

    class_map = {}
    for class_name, class_name_entry in state_class_map.iteritems():
      for subtype, subordinate_list in class_name_entry.iteritems():
        cls = SubordinateClass(name=class_name, subtype=subtype)
        class_map.setdefault(cls, []).extend(str(s) for s in subordinate_list)
    self._state = SubordinateState(
        class_map=class_map,
        unallocated=None)

  def LoadState(self, enforce=True):
    """Loads subordinate pools from the store, replacing the current in-memory set.

    Args:
      enforce (bool): If True, raise an IOError if the state file does not
          exist or a ValueError if it could not be loaded.
    """
    state = {}
    if not os.path.exists(self.state_path):
      if enforce:
        raise IOError("State path does not exist: %s" % (self.state_path,))
    try:
      with open(self.state_path, 'r') as fd:
        state = json.load(fd)
    except (IOError, ValueError):
      if enforce:
        raise
    self.LoadStateDict(state.get('class_map'))

  def SaveState(self):
    """Saves the current subordinate pool set to the store path."""
    state_dict = {}
    if self._state and self._state.class_map:
      class_map = state_dict['class_map'] = {}
      for sc, subordinate_list in self._state.class_map.iteritems():
        class_dict = class_map.setdefault(sc.name, {})
        subtype_dict = class_dict.setdefault(sc.subtype, [])
        subtype_dict.extend(subordinate_list)

    if self._list_unallocated:
      state_dict['unallocated'] = list(self._state.unallocated or ())

    with open(self.state_path, 'w') as fd:
      json.dump(state_dict, fd, sort_keys=True, indent=2)

  def AddPool(self, name, *subordinates):
    """Returns (str): The subordinate pool that was allocated (for chaining).

    Args:
      name (str): The subordinate pool name.
      subordinates: Subordinate name strings that belong to this pool.
    """
    pool = self._pools.get(name)
    if not pool:
      pool = self._pools[name] = set()
    for subordinate in subordinates:
      current_pool = self._all_subordinates.get(subordinate)
      if current_pool is not None:
        if current_pool != name:
          raise ValueError("Cannot register subordinate '%s' with multiple pools "
                           "(%s, %s)" % (subordinate, current_pool, name))
      else:
        self._all_subordinates[subordinate] = name
    pool.update(subordinates)
    return name

  def GetPool(self, name):
    """Returns (frozenset): The contents of the named subordinate pol.

    Args:
      name (str): The name of the pool to query.
    Raises:
      KeyError: If the named pool doesn't exist.
    """
    pool = self._pools.get(name)
    if not pool:
      raise KeyError("No pool named '%s'" % (name,))
    return frozenset(pool)

  def Alloc(self, name, subtype=None, exclusive=True, pools=None, count=1):
    """Returns (SubordinateClass): The SubordinateClass that was allocated.

    Args:
      name (str): The base name of the class to allocate.
      subtype (str): If not None, the class subtype. This, along with the name,
          forms the class ID.
      exclusive (bool): If True, subordinates allocated in this class may not be
          reused in other allocations.
      pools (iterable): If not None, constrain allocation to the named subordinate
          pools.
      count (int): The number of subordinates to allocate for this class.
    """
    # Expand our pools.
    pools = set(pools or ())

    invalid_pools = pools.difference(set(self._pools.iterkeys()))
    assert not invalid_pools, (
        "Class references undefined pools: %s" % (sorted(invalid_pools),))

    cls = SubordinateClass(name=name, subtype=subtype)
    config = SubordinateClassConfig(cls=cls, exclusive=exclusive, pools=pools,
                              count=count)

    # Register this configuration.
    current_config = self._classes.get(cls)
    if current_config:
      # Duplicate allocations must match configurations.
      assert current_config == config, (
          "Class allocation doesn't match current for %s: %s != %s" % (
              cls, config, current_config))
    else:
      self._classes[cls] = config
    return cls

  def Join(self, key, subordinate_class):
    """Returns (SubordinateClass): The 'subordinate_class' passed in (for chaining).

    Args:
      name (str): The key to join to the subordinate class.
      subordinate_class (SubordinateClass): The subordinate class to join.
    """
    self._membership.setdefault(subordinate_class, set()).add(key)
    return subordinate_class

  def _GetSubordinateClassMap(self):
    """Returns (dict): A dictionary mapping SubordinateClass to subordinate tuples.

    Applies the current subordinate configuration to the allocator's subordinate class. The
    result is a dictionary mapping subordinate names to a tuple of keys belonging
    to that subordinate.
    """
    all_subordinates = set(self._all_subordinates.iterkeys())
    n_state = SubordinateState(
        class_map={},
        unallocated=all_subordinates.copy())
    lru = all_subordinates.copy()
    exclusive = set()

    # The remaining classes to allocate. We keep this sorted for determinism.
    remaining_classes = sorted(self._classes.iterkeys())

    def allocate_subordinates(config, subordinates):
      class_subordinates = n_state.class_map.setdefault(config.cls, [])
      if config.count:
        subordinates = subordinates[:max(0, config.count - len(class_subordinates))]
      class_subordinates.extend(subordinates)
      if config.exclusive:
        exclusive.update(subordinates)
      lru.difference_update(subordinates)
      n_state.unallocated.difference_update(subordinates)
      if len(lru) == 0:
        # Reload LRU.
        lru.update(all_subordinates)
      return class_subordinates

    def candidate_subordinates(config, state):
      # Get subordinates from the candidate pools.
      subordinates = set()
      for pool in (config.pools or self._pools.iterkeys()):
        subordinates.update(self._pools[pool])
      if state:
        subordinates &= set(state.class_map.get(config.cls, ()))

      # Remove any subordinates that have been exclusively allocated.
      subordinates.difference_update(exclusive)

      # Deterministically prefer subordinates that haven't been used over those that
      # have.
      return sorted(subordinates & lru) + sorted(subordinates.difference(lru))

    def apply_config(state=None, finite=False):
      incomplete_classes = []
      for subordinate_class in remaining_classes:
        if not self._membership.get(subordinate_class):
          # This subordinate class has no members; ignore it.
          continue
        config = self._classes[subordinate_class]

        if not (finite and config.count is None):
          subordinates = candidate_subordinates(config, state)
        else:
          # We're only applying finite configurations in this pass.
          subordinates = ()
        allocated_subordinates = allocate_subordinates(config, subordinates)
        if len(allocated_subordinates) < max(config.count, 1):
          incomplete_classes.append(subordinate_class)

      # Return the set of classes that still need allocations.
      return incomplete_classes

    # If we have a state, apply as much as possible to the current
    # configuration. Note that anything can change between the saved state and
    # the current configuration, including:
    # - Subordinates added / removed from pools.
    # - Subordinates moved from one pool to another.
    # - Subordinate classes added/removed.
    if self._state:
      remaining_classes = apply_config(self._state)
    remaining_classes = apply_config(finite=True)
    remaining_classes = apply_config()

    # Are there any subordinate classes remaining?
    assert not remaining_classes, (
        "Failed to apply config for subordinate classes: %s" % (remaining_classes,))
    self._state = n_state
    return n_state

  def GetSubordinateMap(self):
    """Returns (dict): A dictionary mapping subordinates to lists of keys.
    """
    subordinate_map_entries = {}
    n_state = self._GetSubordinateClassMap()
    for subordinate_class, subordinates in n_state.class_map.iteritems():
      for subordinate in subordinates:
        entry = subordinate_map_entries.get(subordinate)
        if not entry:
          entry = subordinate_map_entries[subordinate] = SubordinateMapEntry(classes=set(),
                                                           keys=[])
        entry.classes.add(subordinate_class)
        entry.keys.extend(self._membership.get(subordinate_class, ()))

    # Convert SubordinateMapEntry fields to immutable form.
    result = SubordinateMap(
        entries={},
        unallocated=frozenset(n_state.unallocated))
    for k, v in subordinate_map_entries.iteritems():
      result.entries[k] = SubordinateMapEntry(
          classes=frozenset(v.classes),
          keys=tuple(sorted(v.keys)))
    return result
