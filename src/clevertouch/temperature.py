from typing import Optional

class Temperature:
    DEVICE = ""
    CELSIUS = "c"
    FARENHEIT = "f"

    def __init__(
        self,
        temperature: Optional[float],
        unit: str = DEVICE,
        is_writable: bool = False,
        name: str = '(no name)',
    ) -> None:
        self.name: Optional[str] = name
        self.is_writable: bool = is_writable

        if temperature is None:
            self.device: Optional[float] = None
            self.celsius: Optional[float] = None
            self.farenheit: Optional[float] = None
            return None

        elif unit == Temperature.CELSIUS:
            device_temperature = round(18 * temperature + 320)
        elif unit == Temperature.FARENHEIT:
            device_temperature = round(10 * temperature)
        elif unit == Temperature.DEVICE:
            device_temperature = round(temperature)
        else:
            raise Exception("Unknown unit")

        self.device = device_temperature
        self.celsius = (device_temperature - 320) / 18
        self.farenheit = device_temperature / 10

    def as_unit(self, unit: str) -> Optional[float]:
        if unit == Temperature.CELSIUS:
            return self.celsius
        elif unit == Temperature.FARENHEIT:
            return self.farenheit
        elif unit == Temperature.DEVICE:
            return self.device
        raise Exception(f"Unknown unit '{unit}'")

    @classmethod
    def convert(cls, temperature: float, from_unit: str, to_unit: str) -> Optional[float]:
        return Temperature(temperature, from_unit).as_unit(to_unit)

    @classmethod
    def from_celsius(cls, temperature: Optional[float]):
        return Temperature(temperature, Temperature.CELSIUS)

    @classmethod
    def from_farenheit(cls, temperature: Optional[float]):
        return Temperature(temperature, Temperature.FARENHEIT)

    @classmethod
    def from_device(cls, temperature: Optional[float]):
        return Temperature(temperature, Temperature.DEVICE)
