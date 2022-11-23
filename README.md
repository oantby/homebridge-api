# Homie

Python library for querying and controlling
[Homebridge](https://github.com/homebridge/homebridge).
Provides functionality for querying and updating state of homebridge
accessories through the homebridge API, exposed when
[insecure mode is on](https://github.com/oznu/homebridge-config-ui-x/wiki/Enabling-Accessory-Control).

This is inspired by [HomeScript](https://github.com/menahishayan/HomeScript),
but aimed to fill in some gaps it left and correct some assumptions made.

# Usage

Homie looks to provide natural object feel to a homekit interface.
Standard usage follows:

```python
>>> import homebridge_api

>>> HOST='127.0.0.1'
>>> PORT='12345'
>>> AUTH='123-45-678'

>>> h = homebridge_api.Homie(HOST, PORT, AUTH)

>>> h['bedroom light'].on
0

>>> h['bedroom light'].on = True # turns on light

>>> h['bedroom light'].on
1

>>> h['bedroom light'].brightness = 80
```

Accessories are accessed by name as subscripts in a case-insensitive manner.
Their characteristics are accessed as properties of the accessory.

Note: support for accessories is added manually. There's no reason a generic
accessory/service couldn't be made (simply by removing the exception preventing it).
This simply ensures that expectations (required attributes) are met for all
services that have support.