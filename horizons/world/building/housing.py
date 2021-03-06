# ###################################################
# Copyright (C) 2011 The Unknown Horizons Team
# team@unknown-horizons.org
# This file is part of Unknown Horizons.
#
# Unknown Horizons is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# ###################################################

from horizons.gui.tabs import SignalFireOverviewTab
from horizons.world.building.building import BasicBuilding, SelectableBuilding
from horizons.world.building.buildable import BuildableSingle

class Housing(SelectableBuilding, BasicBuilding, BuildableSingle):

	def save(self, db):
		super(Housing, self).save(db)

	def load(self, db, worldid):
		super(Housing, self).load(db, worldid)


class SignalFire(Housing):
	# TODO: range_applies_only_on_island is disabled until #760 is fixed
	# (Big sea tiles cause wrong range highlight)
	#range_applies_only_on_island = False
	tabs = (SignalFireOverviewTab, )