# Copyright: (c) Stéphane Robert (@stephrobert)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Paramètres communs à tous les modules, documentés une fois."""

from __future__ import annotations


class ModuleDocFragment:
    DOCUMENTATION = r"""
options:
  access_key:
    description:
      - Outscale access key.
      - Falls back to the E(OSC_ACCESS_KEY) environment variable, then to the
        profile in C(~/.osc/config.json).
    type: str
  secret_key:
    description:
      - Outscale secret key.
      - Falls back to the E(OSC_SECRET_KEY) environment variable, then to the profile.
    type: str
  region:
    description:
      - Outscale region the request is sent to, for example V(eu-west-2).
      - The API host carries the region (C(api.{region}.outscale.com)), not the path.
      - Falls back to the E(OSC_REGION) environment variable, then to the profile,
        then to V(eu-west-2).
    type: str
  profile:
    description:
      - Name of a profile in C(~/.osc/config.json), the file the Outscale CLIs and SDKs share.
      - Falls back to the E(OSC_PROFILE) environment variable, then to V(default).
    type: str
  api_url:
    description:
      - Full base URL of the API, C(/api/v1) included, overriding the one built from I(region).
      - Meant for a local emulator or a test endpoint.
      - Falls back to the E(OSC_ENDPOINT_API) environment variable, the name the
        C(octl) CLI, the Terraform provider and feint use, then to E(OUTSCALE_API_URL).
    type: str
requirements:
  - osc-sdk-python >= 0.42 (the official Python SDK)
"""

    WAIT = r"""
options:
  wait:
    description:
      - Whether to read the resource until it reaches the state the action leads to.
      - The Outscale API answers at once and the resource changes state afterwards;
        when false, the module returns as soon as the API has accepted the action.
    type: bool
    default: true
  wait_timeout:
    description:
      - Maximum number of seconds to wait for the expected state.
    type: int
    default: 600
"""
