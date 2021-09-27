# Socks Trampoline

## Need

- My netowork admin allowed me only a single inbound port for a website and wont open an SSH for me.
- but I needed more ports, to work from home.
- The fuck with the admin, I got my own socks server running on the inbound port, and now normal HTTP / HTTPS traffic is only redirected, I get my SSH through SOCKS proxy....
- Slick, is it!

# Howto

- Generate a config file.
- Run the trampoline socks proxy on your system.
- That's it.
- Enjoy your socks through 80 or 443.

# TODO

- Improve speed
- Configure the number of threads being spawned
- Dynamically allow multiple internal redirects.

# Contribute

- Fork the repo.
- Open an issue if you face any
- Make a PR
