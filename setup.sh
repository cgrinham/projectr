#!/bin/bash

# Set up Pi for Projectr with Wifi AP

echo "Set up"

echo "Set projector and server to start at login"
echo "

# Check if logged in via SSH, if not run these
if [ -z "$SSH_CLIENT" ] ; then
    python projector.py &
    python server.py &
fi" >> ~/.profile