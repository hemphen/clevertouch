#!/usr/bin/python3
"""Demo of using the object based API abstraction"""
import argparse
import asyncio
import os

from clevertouch import Account, ApiError
from clevertouch.devices import Radiator, OnOffDevice

async def authenticate(email, password, token) -> Account:
    """Authenticate with the cloud API."""
    if email is None:
        raise Exception(
            "Email must be specified, "
            "either with --email or in environment variable CLEVERTOUCH_EMAIL"
        )

    if password is None and token is None:
        raise Exception(
            "Either password or token must be specified. "
            "Token can be set via --token or in environment variable CLEVERTOUCH_TOKEN"
        )

    if password is not None and token is not None:
        print("Both password and token was specified. Preferring password.")
        token = None

    account = Account(email, token)

    if password is not None:
        try:
            # We need to authenticate via cloud
            await account.authenticate(email, password)
        except Exception as ex:
            raise Exception("Authentication failed.") from ex

    return account


async def run_demo(email, password, token) -> None:
    """Run the demo asynchronously"""
    async with await authenticate(email, password, token) as account:
        print(f"The account with email {account.email} was authenticated")

        user = await account.get_user()
        print(f"User id: {user.user_id}")

        for home_id, home_info in user.homes.items():
            print(f"  Home: {home_id}: {home_info.label}")
            home = await account.get_home(home_id)

            for device_id, device in home.devices.items():
                print(f"   Device: {device_id}: {device.label} ({device.device_type})")
                if isinstance(device, Radiator):
                    for temp_name, temp in device.temperatures.items():
                        print(f"      Temp {temp_name} = {temp.celsius:.1f} C")
                if isinstance(device, OnOffDevice):
                    print(f"      {device.device_type} is {'on' if device.is_on else 'off'}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(prog="demo", description="Demo of the library.")
    parser.add_argument(
        "-e", "--email", help="CleverTouch account email", required=False, default=None
    )
    parser.add_argument(
        "-p",
        "--password",
        help="CleverTouch account password",
        required=False,
        default=None,
    )
    parser.add_argument(
        "-t", "--token", help="CleverTouch account token", required=False
    )

    args = parser.parse_args()

    email = args.email or os.environ.get("CLEVERTOUCH_EMAIL", None)
    password = args.password
    token = args.token or os.environ.get("CLEVERTOUCH_TOKEN", None)

    try:
        asyncio.run(run_demo(email, password, token))
    except ApiError as ex:
        print(ex)


if __name__ == "__main__":
    print("Running the demo will communicate with the CleverTouch API.")
    print("It is probably a good idea to avoid calling it to excessively.")
    response = input("Write 'CONNECT' to continue: ")
    if response == "CONNECT":
        main()
