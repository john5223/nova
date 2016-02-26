# Copyright 2013 Intel Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
CPU monitor based on virt driver to retrieve CPU information
"""

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils

from nova.compute.monitors import base
from nova import utils
from nova import exception
from nova.i18n import _LE

CONF = cfg.CONF
CONF.import_opt('compute_driver', 'nova.virt.driver')
LOG = logging.getLogger(__name__)

class SSDDriver(object):
    """
    Driver to obtain which drives are SSD
    """

    def get_ssd_stats(self):
        ssdinfo = {}
        cmd = 'lsblk -d -o name,rota'.split()
        out, err = utils.execute(*cmd)
        if err:
            msg = _('Unable to parse lsblk output.')
            raise exception.NovaException(msg)

        ssd = [line.strip('\n') for line in out.splitlines()]
        for line in ssd[1:]:
            if line.strip():
                name, value = line.split()
                ssdinfo[name] = value.strip()
        return ssdinfo 
        

class Monitor(base.MonitorBase):
    """SSD monitor that uses SSDDriver's get_ssd_stats."""

    def __init__(self, resource_tracker):
        super(Monitor, self).__init__(resource_tracker)
        self.source = CONF.compute_driver
        self.driver = resource_tracker.driver
        self.ssd_driver = SSDDriver()
        self._data = {}
        self._ssd_stats = {}

    def get_metric_names(self):
        self._update_data()
        metrics = [x for x in self._data if x != 'timestamp']
        return metrics

    def get_metric(self, name):
        self._update_data()
        return self._data[name], self._data["timestamp"]

    def _update_data(self):
        # Don't allow to call this function so frequently (<= 10 sec)
        now = timeutils.utcnow()
        if self._data.get("timestamp") is not None:
            delta = now - self._data.get("timestamp")
            if delta.seconds <= 30:
                return

        self._data = {}
        self._data["timestamp"] = now

        # Extract node's CPU statistics.
        try:
            stats = self.ssd_driver.get_ssd_stats()
            for s in stats:
                self._data['drive.{0}.ssd'.format(s)] = stats[s]
            self._ssd_stats = stats.copy()
            LOG.debug("SSD Monitor: %s" % self._data)
        except (NotImplementedError, TypeError, KeyError):
            LOG.exception(_LE("Not all properties needed are implemented "
                              "in the ssd driver"))
            raise exception.ResourceMonitorError(
                monitor=self.__class__.__name__)

