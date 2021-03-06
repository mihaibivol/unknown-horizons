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

import logging
import textwrap

from horizons.gui.modules import PlayerDataSelection
from horizons.savegamemanager import SavegameManager
from horizons.network.networkinterface import MPGame
from horizons.constants import MULTIPLAYER
from horizons.network.networkinterface import NetworkInterface
from horizons.network import find_enet_module

enet = find_enet_module()

class MultiplayerMenu(object):
	log = logging.getLogger("networkinterface")

	def show_multi(self):
		"""Shows main multiplayer menu"""
		if enet == None:
			headline = _(u"Unable to find pyenet")
			descr = _(u"The multiplayer feature requires the library \"pyenet\", which couldn't be found on your system.")
			advice = _(u"Linux users: Try to install pyenet through your package manager.") + "\n" + \
						 _(u"Windows users: There is currently no reasonable support for Windows.")
			self.show_error_popup(headline, descr, advice)
			return

		if NetworkInterface() is None:
			try:
				NetworkInterface.create_instance()
			except RuntimeError, e:
				headline = _(u"Failed to initialize networking.")
				descr = _(u"Networking couldn't be initialised with the current configuration.")
				advice = _(u"Check the data you entered in the Network section in the settings dialogue.")
				self.show_error_popup(headline, descr, advice, unicode(e))
				return

		if not NetworkInterface().isconnected():
			connected = self.__connect_to_server()
			if not connected:
				return

		if NetworkInterface().isjoined():
			if not NetworkInterface().leavegame():
				return

		event_map = {
			'cancel'  : self.__cancel,
			'join'    : self.__join_game,
			'create'  : self.__show_create_game,
			'refresh' : self.__refresh,
			'apply_new_nickname' : self.__apply_new_nickname
		}
		self.widgets.reload('multiplayermenu')
		self._switch_current_widget('multiplayermenu', center=True, event_map=event_map, hide_old=True)

		refresh_worked = self.__refresh()
		if not refresh_worked:
			self.show_main()
			return
		self.current.findChild(name='gamelist').capture(self.__update_game_details)
		self.current.findChild(name='showonlyownversion').capture(self.__show_only_own_version_toggle)
		self.current.playerdata = PlayerDataSelection(self.current, self.widgets)

		self.current.show()

		self.on_escape = event_map['cancel']

	def __connect_to_server(self):
		NetworkInterface().register_chat_callback(self.__receive_chat_message)
		NetworkInterface().register_game_details_changed_callback(self.__update_game_details)
		NetworkInterface().register_game_prepare_callback(self.__prepare_game)
		NetworkInterface().register_game_starts_callback(self.__start_game)
		NetworkInterface().register_error_callback(self.__on_error)
		NetworkInterface().register_player_joined_callback(self.__player_joined)
		NetworkInterface().register_player_left_callback(self.__player_left)
		NetworkInterface().register_player_changed_name_callback(self.__player_changed_name)

		try:
			NetworkInterface().connect()
		except Exception, err:
			self.show_popup(_("Network Error"), _("Could not connect to master server. Please check your Internet connection. If it is fine, it means our master server is temporarily down.\nDetails: %s") % str(err))
			return False
		return True

	def __apply_new_nickname(self):
		new_nick = self.current.playerdata.get_player_name()
		NetworkInterface().change_name(new_nick)

	def __on_error(self, exception, fatal=True):
		"""Error callback"""
		if fatal and self.session is not None:
			self.session.timer.ticks_per_second = 0
		if self.dialog_executed:
			# another message dialog is being executed, and we were called by that action.
			# if we now trigger another message dialog, we will probably loop.
			return
		if not fatal:
			self.show_popup(_("Error"), unicode(exception))
		else:
			self.show_popup(_("Fatal Network Error"), \
		                 _("Something went wrong with the network:") + u'\n' + \
		                 unicode(exception) )
			self.quit_session(force=True)

	def __cancel(self):
		if NetworkInterface().isconnected():
			NetworkInterface().disconnect()
		self.show_main()

	def __refresh(self):
		"""Refresh list of games.
		Only possible in multiplayer main menu state.
		@return bool, whether refresh worked"""
		self.games = NetworkInterface().get_active_games(self.current.findChild(name='showonlyownversion').marked)
		if self.games is None:
			return False
		self.current.distributeInitialData({'gamelist' : map(lambda x: "%s (%u, %u)%s"%(x.get_map_name(), x.get_player_count(), x.get_player_limit(), " " + _("Version differs!") if x.get_version() != NetworkInterface().get_clientversion() else ""), self.games)})
		self.current.distributeData({'gamelist' : 0}) # select first map
		self.__update_game_details()
		return True

	def __get_selected_game(self):
		try:
			if NetworkInterface().isjoined():
				return NetworkInterface().get_game()
			else:
				index = self.current.collectData('gamelist')
				return self.games[index]
		except:
			return MPGame(-1, "", "", 0, 0, [], "", -1)

	def __show_only_own_version_toggle(self):
		self.__refresh()

	def __update_game_details(self, game = None):
		"""Set map name and other misc data in a widget. Only possible in certain states"""
		if game == None:
			game = self.__get_selected_game()
		self.current.findChild(name="game_map").text = _("Map: ") + game.get_map_name()
		self.current.findChild(name="game_playersnum").text =  _("Players: ") + \
				unicode(game.get_player_count()) + u"/" + unicode(game.get_player_limit())
		creator_text = self.current.findChild(name="game_creator")
		creator_text.text = _("Creator: ") + unicode(game.get_creator())
		creator_text.adaptLayout()
		textplayers = self.current.findChild(name="game_players")
		if textplayers is not None:
			textplayers.text = u", ".join(game.get_players())

		vbox = self.current.findChild(name="gamedetailsbox")
		if vbox is not None:
			vbox.adaptLayout()

	def __join_game(self, game = None):
		"""Joins a multiplayer game. Displays lobby for that specific game"""
		if game == None:
			game = self.__get_selected_game()
		if game.get_uuid() == -1: # -1 signals no game
			return
		if game.get_version() != NetworkInterface().get_clientversion():
			self.show_popup(_("Wrong version"), _("The game's version differs from your version. Every player in a multiplayer game must use the same version. This can be fixed by every player updating to the latest version. Game version: %(gameversion)s Your version: %(ownversion)s") % {'gameversion': game.get_version(), 'ownversion': NetworkInterface().get_clientversion()})
			return
		# acctual join
		join_worked = NetworkInterface().joingame(game.get_uuid())
		if not join_worked:
			return
		self.__show_gamelobby()

	def __prepare_game(self, game):
		self._switch_current_widget('loadingscreen', center=True, show=True)
		import horizons.main
		horizons.main.prepare_multiplayer(game)

	def __start_game(self, game):
		import horizons.main
		horizons.main.start_multiplayer(game)

	def __show_gamelobby(self):
		"""Shows lobby (gui for waiting until all players have joined). Allows chatting"""
		event_map = {
			'cancel' : self.show_multi,
		}
		game = self.__get_selected_game()
		self.widgets.reload('multiplayer_gamelobby') # remove old chat messages, etc
		self._switch_current_widget('multiplayer_gamelobby', center=True, event_map=event_map, hide_old=True)

		self.__update_game_details(game)
		self.current.findChild(name="game_players").text = u", ".join(game.get_players())
		textfield = self.current.findChild(name="chatTextField")
		textfield.capture(self.__send_chat_message)
		textfield.capture(self.__chatfield_onfocus, 'mouseReleased', 'default')
		self.current.show()

		self.on_escape = event_map['cancel']

	def __chatfield_onfocus(self):
		textfield = self.current.findChild(name="chatTextField")
		textfield.text = u""
		textfield.capture(None, 'mouseReleased', 'default')

	def __send_chat_message(self):
		"""Sends a chat message. Called when user presses enter in the input field"""
		msg = self.current.findChild(name="chatTextField").text
		if len(msg):
			self.current.findChild(name="chatTextField").text = u""
			NetworkInterface().chat(msg)

	def __receive_chat_message(self, game, player, msg):
		"""Receive a chat message from the network. Only possible in lobby state"""
		line_max_length = 40
		chatbox = self.current.findChild(name="chatbox")
		full_msg = u""+ player + ": "+msg
		lines = textwrap.wrap(full_msg, line_max_length)
		for line in lines:
			chatbox.items.append(line)
		chatbox.selected = len(chatbox.items) - 1

	def __print_event_message(self, msg):
		line_max_length = 40
		chatbox = self.current.findChild(name="chatbox")
		full_msg = u"* " + msg + " *"
		lines = textwrap.wrap(full_msg, line_max_length)
		for line in lines:
			chatbox.items.append(line)
		chatbox.selected = len(chatbox.items) - 1

	def __player_joined(self, game, player):
		self.__print_event_message("%s has joined the game" % (player.name))

	def __player_left(self, game, player):
		self.__print_event_message("%s has left the game" % (player.name))

	def __player_changed_name(self, game, plold, plnew, myself):
		if myself:
			self.__print_event_message("You are now known as %s" % (plnew.name))
		else:
			self.__print_event_message("%s is now known as %s" % (plold.name, plnew.name))

	def __show_create_game(self):
		"""Shows the interface for creating a multiplayer game"""
		event_map = {
			'cancel' : self.show_multi,
			'create' : self.__create_game
		}
		self._switch_current_widget('multiplayer_creategame', center=True, event_map=event_map, hide_old=True)

		self.current.files, self.maps_display = SavegameManager.get_maps()
		self.current.distributeInitialData({
			'maplist' : self.maps_display,
			'playerlimit' : range(2, MULTIPLAYER.MAX_PLAYER_COUNT)
		})
		def _update_infos():
			mapindex = self.current.collectData('maplist')
			mapfile = self.current.files[mapindex]
			number_of_players = SavegameManager.get_recommended_number_of_players( mapfile )
			self.current.findChild(name="recommended_number_of_players_lbl").text = \
					_("Recommended number of players: ") + unicode( number_of_players )
		if len(self.maps_display) > 0: # select first entry
			self.current.distributeData({
				'maplist' : 0,
				'playerlimit' : 0
			})
			_update_infos()
		self.current.show()

		self.on_escape = event_map['cancel']

	def __create_game(self):
		"""Actually create a game, join it and display the lobby"""
		# create the game
		#TODO: possibly some input validation
		mapindex = self.current.collectData('maplist')
		mapname = self.maps_display[mapindex]
		maxplayers = self.current.collectData('playerlimit') + 2 # 1 is the first entry
		game = NetworkInterface().creategame(mapname, maxplayers)
		if game is None:
			return

		self.__show_gamelobby()
