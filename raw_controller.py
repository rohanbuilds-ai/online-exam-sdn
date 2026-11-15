#!/usr/bin/env python3
"""
SDN OpenFlow 1.3 Controller Entry Point.
Delegates to modular sdn.controller with dynamic congestion management.
"""
import sys
from sdn.controller import main

if __name__ == "__main__":
    main()
