# OvFietsBackend
This service fetches the latest OV-fiets data and makes it available via a REST API.

It pulls data from OpenOV, but with a few perks over directly using http://fiets.openov.nl/locaties.json:

- Automatically removes outdated entries
- only the essential info for quick overviews (for details, you can follow the provided link)
- Data is delivered as a simple array, instead of a map with unnecessary IDs
- Can be hosted over HTTPS (contributions welcome!)

Also, OpenOV isn’t thrilled about heavy traffic on their JSON (they provide open data, not hosting). They’d rather you use the ZeroMQ service bus and host it yourself, which is exactly what this project does.

## Hosting it ##
This is designed to be hosted as easlily as possible, while reducing hosting costs to zero when possible. That's why Google Cloud is chosen: services like AWS also have a free tier, but after a year you have to pay. This restriction doesn't apply for Google Cloud. Still this software comes with no warranties whatsoever, so do keep an eye out for your costs. 

Hosting is really easy: after setting up Google Cloud, you only need to do a `terraform apply` and a completely working backend will be deployed.

## Usage ##
This backend is used by [cristan/OvFietsBeschikbaarheidApp](https://github.com/cristan/OvFietsBeschikbaarheidApp).

Happy hosting!
