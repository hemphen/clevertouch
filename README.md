# CleverTouch - interact with Touch E3-connected radiators

This Python API enables control and monitoring of Touch E3-connected radiators via CleverTouch cloud accounts.

## Background

LVI by Purmo is range of radiators manufactured by the Finnish company Purmo.
Some models, such as Yali Digital, Parada and Ramo may be monitored and controlled
centrally using the optional accessory TempCo Touch E3. The Touch E3 may in turn be
controlled remotely via a CleverTouch cloud account and related mobile and web apps.

## General usage

All communication with the cloud API is asynchronous using `aiohttp`. Communication
can either use lower-level calls using an `ApiSession` object with methods for returning unparsed data objects, or a higher-lever object model using the `Account` with
friendly functions and objects for the most relevant properties of homes and devices.

The _most_ useful methods/properties of the _most_ relevant objects are listed below. A full description of the functionality is only available by reading the source
code. 

## Using the higher-level API

See [samples/demo.py](https://github.com/hemphen/clevertouch/blob/samples/demo.py) for a basic but functional example of how to use the higher-level API.

### The `Account` object

| Methods | Description |
| --- | --- |
| `Account()` | Create an `Account` object. |
| `authenticate(email, password)` | Authenticate with the service. |
| `get_user()` | Returns a refreshable `User` object containing info about all available homes. |
| `get_home(id)` | Returns a refreshable `Home` object for a home with the specific `id`. |
| `get_homes()` | Returns a list of all homes registered with the user. |

### The `User` object
| Properties/Methods | Description |
| --- | --- |
| `homes` | Dictionary containing id and basic information about all available homes. |
| `refresh()` | Refreshes the data from the cloud account. |

### The `Home` object
| Properties/Methods | Description |
| --- | --- |
| `info` | Provides an object with basic info about the home. |  
| `devices` | A list with all available devices. |
| `refresh()` | Refreshes the data from the cloud account. |

### The `Radiator` object
| Properties/Methods | Description |
| --- | --- |
| `label` | The user-specified name of the radiator. |
| `zone` | Info about the zone where the radiator is located. |
| `temperatures` | A dictionary with temperatures. |
| `heat_mode` | The current heat mode. |
| `set_temperature(name,value,unit)` | Send a request to update a temperature setting. |
| `set_heat_mode(heat_mode)` | Send a request to update the heat mode. |

## Using the lower-level API

### The `ApiSession` object

| Methods | Description |
| --- | --- |
| `ApiSession()` | Create an API session. |
| `authenticate(email, password)` | Authenticate with the service. |
| `read_user_data()` | Return unparsed data about the user associated with the account. |
| `read_home_data(id)` | Return unparsed data about the home with the specified id. |
| `write_query(id, params)` | Send a raw update query for a specific home |  

## Integrations

This API was primarily written to be able to integrate Touch E3-radiators in Home Assistant, see https://github.com/hemphen/hass-clevertouch.
