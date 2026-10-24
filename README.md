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

## Other brands

While untested, a number of other product lines seem to be using the same controller and software with different branding.

Applications using the following URLs might work, fully or partially, by specifying the `host` argument when creating an `Account` or `ApiSession` (see below).

* Walter Meier Metalplast smart-comfort - [https://www.smartcomfort.waltermeier.com](https://www.smartcomfort.waltermeier.com)
* Frico PF Smart - [https://fricopfsmart.frico.se](https://fricopfsmart.frico.se)
* Fenix V24 Wifi - [https://v24.fenixgroup.eu](https://v24.fenixgroup.eu)
* Vogel & Noot E3 App - [https://e3.vogelundnoot.com](https://e3.vogelundnoot.com)
* CordiVari My Way Cosy Home - [https://cordivarihome.com](https://cordivarihome.com)

Additionally, Watts Vision ([https://smarthome.wattselectronics.com](https://smarthome.wattselectronics.com)) uses the same app but a different/improved authentication process. Work is needed to support
that process within this library.

## Other implementations / GitHub repositories

There are available alternative implementations with unknown status of functionality available on GitHub.

* Watts Vision support for Home Assistant is provided through the repo [pwesters/watts_vision](https://github.com/pwesters/watts_vision/).
* A Watts Vision library is also available in [mjkl-gh/aio-watts-vision](https://github.com/mjkl-gh/aio-watts-vision).
* Library support for LVI heaters can be found in [hwaastad/pylvi](https://github.com/hwaastad/pylvi) with Home Assistant support in [hwaastad/lvi](https://github.com/hwaastad/lvi).
* An alternative solution to support Home Assistant by streaming values via MQTT is available in [komppa/tempco2mqtt](https://github.com/komppa/tempco2mqtt).

## Using the higher-level API

See [samples/demo.py](samples/demo.py) for a basic but functional example of how to use the higher-level API.

### The `Account` object

| Methods | Description |
| --- | --- |
| `Account(email=None, token=None, *, host=None, session=None)` | Create an account. The host is a bare hostname, such as `e3.lvi.eu` (the default), without `https://` or a path. |
| `authenticate(email, password)` | Authenticate with the service. |
| `get_user()` | Returns a refreshable `User` object containing info about all available homes. |
| `get_home(id)` | Returns a refreshable `Home` object for a home with the specific `id`. |
| `get_homes()` | Returns a list of all homes registered with the user. |

Getters cache successfully fetched user and home objects. Call `await user.refresh()`
or `await home.refresh()` to fetch current data; repeated getters reuse the cached
objects. Successful password authentication clears both account caches.

Use `await account.authenticate(email, password)` for password login, or create
`Account(email, token=refresh_token)` to use a stored refresh token. Access tokens
are refreshed automatically when expired, on the next API request. The server may
rotate the refresh token; persist the latest `account.api.refresh_token` after
operations that can refresh it, even if a subsequent data request fails. The
library does not persist tokens for you.

### The `User` object
| Properties/Methods | Description |
| --- | --- |
| `homes` | Dictionary mapping home IDs to `HomeInfo` objects. |
| `refresh()` | Refreshes the data from the cloud account. |

### The `Home` object
| Properties/Methods | Description |
| --- | --- |
| `info` | Provides an object with basic info about the home. |  
| `devices` | Dictionary mapping device IDs to device objects. |
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
| `ApiSession(email=None, refresh_token=None, *, host=None, manufacturer=None, session=None)` | Create an API session. Use a bare hostname for `host`; the default is `e3.lvi.eu`. |
| `authenticate(email, password)` | Authenticate with the service. |
| `read_user_data()` | Return unparsed data about the user associated with the account. |
| `read_home_data(id)` | Return unparsed data about the home with the specified id. |
| `write_query(id, params)` | Send a raw update query for a specific home |  

## Integrations

This API was primarily written to be able to integrate Touch E3-radiators in Home Assistant, see https://github.com/hemphen/hass-clevertouch.

## Testing

Install the library and test dependencies with
`python3 -m pip install . pytest pytest-asyncio python-dotenv`, then run
`python3 -m pytest`. Live account tests are skipped by default.

To run live tests explicitly, configure `CLEVERTOUCH_EMAIL` and
`CLEVERTOUCH_PASSWORD` in the environment or `.env`, then run
`python3 -m pytest --live -m live`.
