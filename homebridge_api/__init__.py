import requests
import sys
import time
import os

from pprint import pprint
from abc import ABC, abstractmethod

class ApiException(RuntimeError):
	pass

class UselessService(RuntimeError):
	"""
	Raised to prevent a useless service from being added to the
	services list.
	"""
	pass

class Homie:
	
	refresh_time = 30.0
	
	def __init__(self, host, port, auth, **kwargs):
		self._base = f'http://{host}:{port}/'
		self._headers = {
			'Content-Type': 'application/json',
			'Authorization': auth
		}
		self._accessories = []
		self._last_update = 0
		
		self.load_accessories()
	
	def load_accessories(self):
		r = requests.get(self._base + 'accessories', headers=self._headers)
		if r.status_code != 200:
			raise ApiException('Got unexpected response code %d' % r.status_code)
		
		self._last_update = time.time()
		
		j = None
		try:
			j = r.json()
		except:
			raise ApiException('Failed to decode response data')
		
		if 'accessories' not in j:
			raise ApiException('No accessories found in API data')
		
		for x in j['accessories']:
			try:
				self._accessories.append(Accessory(x, self))
			except ApiException as e:
				pass
	
	@property
	def accessories(self):
		if time.time() > self._last_update + self.refresh_time:
			self.load_accessories()
		return self._accessories
	
	def __getitem__(self, key):
		if time.time() > self._last_update + self.refresh_time:
			self.load_accessories()
		for x in self._accessories:
			if type(x.name) == str and x.name.lower() == key.lower():
				return x
		raise KeyError(key)

class Accessory:
	def __init__(self, data, homie):
		self.__dict__['_base'] = homie._base
		self.__dict__['_headers'] = homie._headers
		self.__dict__['_name'] = None
		
		if 'aid' not in data:
			raise ApiException('Accessory had no aid')
		
		self.__dict__['_aid'] = data['aid']
		self.__dict__['_services'] = []
		svcs = data.get('services', []);
		for x in svcs:
			try:
				self._services.append(Service.make(x, self))
			except UselessService as e:
				# we don't want to store that service. this is not an error.
				pass
	@property
	def name(self):
		return self._name
	
	def setChar(self, iid, val, tries=3):
		for i in range(tries):
			r = requests.put(self._base + 'characteristics', headers=self._headers,
				json={'characteristics': [{'aid': self._aid, 'iid': iid, 'value': val}]})
			if r.status_code in [200, 204, 207]:
				return True
			elif r.status_code >= 400 and r.status_code < 500:
				# no point retrying that one
				return False
			elif i == tries - 1:
				return False # skip the last sleep
			time.sleep(2**i)
	
	def turnOn(self, val=1):
		for x in self._services:
			if iid := getattr(x, 'onIid', None):
				self.setChar(iid, val)
				x.on = bool(val)
	
	def turnOff(self):
		self.turnOn(0)
	
	def __setattr__(self, name, val):
		if name == 'on':
			return self.turnOn(int(val))
		
		for x in self._services:
			if iid := getattr(x, name + 'Iid', None):
				self.setChar(iid, val)
				x[name] = val
	
	def __repr__(self):
		s = 'Accessory('
		if self.name is None:
			s += 'Unnamed,'
		else:
			s += f'name={self.name},'
		if 'on' in self.__dict__:
			s += ('On' if self.on else 'Off') + ','
		if 'brightness' in self.__dict__:
			s += f'brightness={self.brightness},'
		for x in self._services:
			for attr in x._required_attributes:
				if attr not in ['on', 'brightness']:
					s += f'{attr}={x.__dict__[attr]},'
		
		return s[:-1] + ')'

class Service(ABC):
	def make(data, parent):
		# my types:
		# {'112', '4A', '110', '3E', 'E863F007-079E-48FF-8F27-9C2605A29F52', '43', '49', 'A2'}
		dtype = data.get('type')
		
		if dtype == '43':
			return LightBulbService(data, parent)
		elif dtype == '112':
			return MicrophoneService(data, parent)
		elif dtype == '4A':
			return ThermostatService(data, parent)
		elif dtype == '49':
			return SwitchService(data, parent)
		elif dtype == '47':
			return OutletService(data, parent)
		elif dtype == '3E':
			# extracts name
			tmp = Service(data, parent)
			raise UselessService('Info Service. Unwanted')
		else:
			raise UselessService('Unknown service type "%s"' % dtype)
	
	def __setitem__(self, name, val):
		self.__dict__[name] = val
	
	def __init__(self, data=None, parent=None):
		if not data: return
		if '_parent' not in self.__dict__:
			self._parent = parent
		if '_required_attributes' not in self.__dict__:
			self._required_attributes = []
		
		for x in data['characteristics']:
			name = x['description'].replace(' ', '')
			name = name[0].lower() + name[1:]
			if (('pw' in x.get('perms', []) and 'value' in x)
				or name in self._required_attributes):
				self[name] = x['value']
				self[name + 'Iid'] = x['iid']
				self._parent.__dict__[name] = x['value']
			elif name == 'name':
				self._parent.__dict__['_name'] = x['value']
		
		for attr in self._required_attributes:
			if attr not in self.__dict__ or f'{attr}Iid' not in self.__dict__:
				print(f'Required characteristic {attr} not defined')
				pprint(data)
				raise ApiException(f'Required characteristic {attr} not defined')
	
	def _notSupportedFunc(self):
		raise NotSupported('Not supported by this service')

class LightBulbService(Service):
	
	def __init__(self, data, parent):
		# On is required.
		
		self._required_attributes = ['on']
		
		super().__init__(data, parent)

class MicrophoneService(Service):
	
	def __init__(self, data, parent):
		self._required_attributes = ['mute']
		super().__init__(data, parent)

class ThermostatService(Service):
	OFF = 0
	HEAT = 1
	COOL = 2
	AUTO = 3
	
	CELSIUS = 0
	FAHRENHEIT = 1
	def __init__(self, data, parent):
		self._required_attributes = [
			'currentHeatingCoolingState',
			'targetHeatingCoolingState',
			'currentTemperature',
			'targetTemperature',
			'temperatureDisplayUnits']
		super().__init__(data, parent)
	
	def __repr__(self):
		stat = 'ThermostatService('
		if self.targetHeatingCoolingState == ThermostatService.OFF:
			stat += 'Off,'
		elif self.targetHeatingCoolingState == ThermostatService.HEAT:
			stat += 'Heat,'
		elif self.targetHeatingCoolingState == ThermostatService.COOL:
			stat += 'Cool,'
		else:
			stat += 'Auto,'
		
		stat += 'Target=%.02f,' % self.targetTemperature
		stat += 'Present=%.02f)' % self.currentTemperature
		return stat

class SwitchService(Service):
	def __repr__(self):
		return f'SwitchService(On={self.on})'
	
	def __init__(self, data, parent):
		self._required_attributes = ['on']
		super().__init__(data, parent)

class OutletService(Service):
	def __repr__(self):
		return f'SwitchService(On={self.on})'
	
	def __init__(self, data, parent):
		self._required_attributes = ['on']
		super().__init__(data, parent)
