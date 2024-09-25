# OvFietsBackend
This service fetches the latest OV-fiets data and makes it available via a REST API.

It pulls data from OpenOV, but with a few perks over directly using http://fiets.openov.nl/locaties.json:

- Automatically removes outdated entries
- only the essential info for quick overviews (for details, you can follow the provided link)
- Data is delivered as a simple array, instead of a map with unnecessary IDs
- Can be hosted over HTTPS (contributions welcome!)

Also, OpenOV isn’t thrilled about heavy traffic on their JSON (they provide open data, not hosting). They’d rather you use the ZeroMQ service bus and host it yourself, which is exactly what this project does.

Happy hosting!