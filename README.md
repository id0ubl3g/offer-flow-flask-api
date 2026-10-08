# Offer Flow Flask API

<!-- markdownlint-disable MD033 -->

<div align="center">
  <img src=".github/abacus.png" alt="Abacus Logo" width="130">
  <h1><b>Offer Flow Flask API</b></h1>
  <p>Flask API to register product offers and dispatch them to WhatsApp groups on a schedule.</p>
  <p>
    <img src="https://img.shields.io/github/last-commit/id0ubl3g/offer-flow-flask-api?style=flat&logo=git&logoColor=white&color=7c5cfc" alt="Last Commit">
    <img src="https://img.shields.io/github/languages/top/id0ubl3g/offer-flow-flask-api?style=flat&color=7c5cfc" alt="Top Language">
    <img src="https://img.shields.io/github/languages/count/id0ubl3g/offer-flow-flask-api?style=flat&color=7c5cfc" alt="Languages Count">
  </p>
</div>

<!-- markdownlint-enable MD033 -->

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Manual Installation (Ubuntu/Debian)](#manual-installation-ubuntudebian)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
  - [Endpoints](#endpoints)
  - [Core Endpoints](#core-endpoints)
    - [Create Offer Endpoint](#create-offer-endpoint)
    - [Upload Offer Image Endpoint](#upload-offer-image-endpoint)
    - [Connect WhatsApp Endpoint](#connect-whatsapp-endpoint)
    - [Update Group Endpoint](#update-group-endpoint)
    - [Create Schedule Endpoint](#create-schedule-endpoint)
    - [Queue Offer Endpoint](#queue-offer-endpoint)
  - [Example Use Case](#example-use-case)
    - [From Offer to Scheduled Dispatch](#from-offer-to-scheduled-dispatch)
- [How Dispatching Works](#how-dispatching-works)
- [License](#license)

## Overview

The Offer Flow Flask API is a multi-tenant backend developed with Flask that lets each user register product offers (link, name, message, price, discount and image), connect their own WhatsApp number and choose which groups receive the promotions. Offers wait in a queue and a background worker sends the next one at every configured time, group after group, with random delays to reduce the risk of the number being blocked.

## Features

- Supabase authentication with register, login, refresh tokens, password reset and account deletion
- Access tokens verified locally with the project JWKS (ES256)
- Offer management with prices in cents, discount calculated by the database and WhatsApp-ready message templates
- Offer image upload to Supabase Storage with content-based type validation
- WhatsApp connection through Evolution API using QR code, one instance per user
- Group sync with admin detection, so groups where only admins can send are blocked automatically
- Offer queue and weekly schedules per user, in the user's timezone
- Background worker with Redis lock, random delays between groups, daily limit and retry
- Dispatch history per group with manual retry of failed sends
- Row Level Security on every table, rate limiting and temporary blocking after repeated violations

## Project Structure

```plaintext
└── offer-flow-flask-api/
  ├── .github/
  │   └── abacus.png
  ├── config/
  │   └── providers/
  │       ├── initialize_evolution.py
  │       ├── initialize_limiter.py
  │       ├── initialize_redis.py
  │       └── initialize_supabase.py
  ├── scripts/
  │   └── connect_whatsapp.py
  ├── src/
  │   ├── api/
  │   │   ├── app.py
  │   │   ├── errors.py
  │   │   └── routes/
  │   │       ├── auth.py
  │   │       ├── dispatches.py
  │   │       ├── offers.py
  │   │       ├── profile.py
  │   │       ├── schedules.py
  │   │       ├── webhooks.py
  │   │       └── whatsapp.py
  │   ├── middlewares/
  │   │   └── auth.py
  │   ├── schemas/
  │   │   ├── offer_schema.py
  │   │   ├── schedule_schema.py
  │   │   └── whatsapp_schema.py
  │   ├── services/
  │   │   ├── auth_service.py
  │   │   ├── dispatch_service.py
  │   │   ├── evolution_client.py
  │   │   ├── offer_service.py
  │   │   ├── rate_limit_service.py
  │   │   ├── schedule_service.py
  │   │   └── whatsapp_service.py
  │   ├── utils/
  │   │   ├── return_responses.py
  │   │   ├── send_email_verification.py
  │   │   └── system_utils.py
  │   ├── worker/
  │   │   └── dispatcher.py
  │   └── extensions.py
  ├── supabase/
  │   └── migrations/
  ├── .env.example
  ├── .gitignore
  ├── docker-compose.yml
  ├── LICENSE
  ├── Makefile
  ├── README.md
  ├── requirements.txt
  ├── run.py
  └── worker.py
```

## Prerequisites

To run the Offer Flow Flask API, use Ubuntu 22.04, 24.04 or 26.04 (or a similar Debian-based system) with Python 3.10 or higher. The environment must include Docker and Docker Compose for the containerized services (Redis, Postgres and Evolution API), Node.js to run the Supabase CLI, a Supabase project for authentication, database and storage, and internet access for Supabase, WhatsApp and email SMTP.

## Manual Installation (Ubuntu/Debian)

Update system & install base dependencies

```sh
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git lsof nodejs npm
```

### Install Docker

Install Docker and Docker Compose from the Ubuntu repositories:

```sh
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Log out and log back in so Docker can be used without `sudo`. For other systems, follow the official guide: [https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)

## Environment Configuration

Configure environment variables

```sh
cp .env.example .env
```

Configure the required environment variables in `.env`:

| Variable | Description |
| -------- | ----------- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key, used only by the backend |
| `REDIS_PASSWORD` | Password for the Redis container |
| `REDIS_URL` | `redis://default:<REDIS_PASSWORD>@localhost:6379/0` |
| `sender_email` | Gmail account used to send password reset codes |
| `sender_password` | Gmail app password |
| `EVOLUTION_API_URL` | Evolution API URL, `http://localhost:8080` by default |
| `EVOLUTION_API_KEY` | Global Evolution API key |
| `EVOLUTION_POSTGRES_PASSWORD` | Password for the Evolution Postgres container |
| `EVOLUTION_WEBHOOK_SECRET` | Secret used to sign the per-instance webhook header |
| `APP_WEBHOOK_BASE_URL` | URL the Evolution container uses to reach the API, `http://host.docker.internal:5000` by default |

Generate the secrets with:

```sh
openssl rand -hex 32
```

Sensitive credentials should not be committed to the repository.

## Database Setup

The schema, Row Level Security policies and the `offer-images` storage bucket live in `supabase/migrations`. Link the project once and apply the migrations:

```sh
npx supabase login
npx supabase link --project-ref <project-ref>
make migrate
```

## Running the Application

```sh
git clone https://github.com/id0ubl3g/offer-flow-flask-api
cd offer-flow-flask-api
make run
```

The `make run` command creates the virtual environment, installs dependencies, frees the API port, starts Docker services (Redis, Postgres and Evolution API), launches the Flask API on `http://localhost:5000` and runs the Dispatch Worker.

| Command | Description |
| ------- | ----------- |
| `make run` | Install, start Docker, API and worker |
| `make stop` | Stop the API and the worker |
| `make api` | Restart only the API |
| `make worker` | Restart only the worker |
| `make docker-up` | Start Redis, Postgres and Evolution API |
| `make docker-down` | Stop the containers |
| `make migrate` | Apply the Supabase migrations |

To connect a WhatsApp number from the terminal, run:

```sh
.venv/bin/dotenv run -- .venv/bin/python scripts/connect_whatsapp.py
```

## API Documentation

### Endpoints

| Method   | Endpoint                               | Description                                                  |
| -------- | -------------------------------------- | ------------------------------------------------------------ |
| `POST`   | `/auth/register`                       | Registers a new user.                                        |
| `POST`   | `/auth/login`                          | Logs in and returns access and refresh tokens.               |
| `POST`   | `/auth/refresh`                        | Refreshes the session using the refresh token.               |
| `POST`   | `/auth/forgot-password`                | Sends a 6-character recovery code by email.                  |
| `POST`   | `/auth/reset-password`                 | Verifies the code and updates the password.                  |
| `DELETE` | `/auth/delete-account`                 | Deletes the account, images and WhatsApp instance.           |
| `GET`    | `/profile`                             | Returns user profile data.                                   |
| `GET`    | `/offers`                              | Lists offers with `status`, `page` and `per_page` filters.   |
| `POST`   | `/offers`                              | Creates an offer.                                            |
| `GET`    | `/offers/<offer_id>`                   | Returns an offer.                                            |
| `PATCH`  | `/offers/<offer_id>`                   | Updates an offer or archives it.                             |
| `DELETE` | `/offers/<offer_id>`                   | Deletes an offer and its image.                              |
| `PUT`    | `/offers/<offer_id>/image`             | Uploads or replaces the offer image.                         |
| `DELETE` | `/offers/<offer_id>/image`             | Removes the offer image.                                     |
| `GET`    | `/offers/<offer_id>/preview`           | Returns the rendered WhatsApp message.                       |
| `POST`   | `/offers/<offer_id>/test-send`         | Sends the offer to one group right away.                     |
| `GET`    | `/offers/queue`                        | Lists queued offers in dispatch order.                       |
| `POST`   | `/offers/<offer_id>/queue`             | Adds the offer to the end of the queue.                      |
| `DELETE` | `/offers/<offer_id>/queue`             | Removes the offer from the queue.                            |
| `GET`    | `/whatsapp`                            | Returns the connection status and the current QR code.       |
| `POST`   | `/whatsapp/connect`                    | Creates the WhatsApp instance or generates a new QR code.    |
| `POST`   | `/whatsapp/disconnect`                 | Logs the number out.                                         |
| `DELETE` | `/whatsapp`                            | Deletes the instance and its groups.                         |
| `POST`   | `/whatsapp/groups/sync`                | Syncs the groups of the connected number.                    |
| `GET`    | `/whatsapp/groups`                     | Lists groups, optionally filtered by `active`.               |
| `PATCH`  | `/whatsapp/groups/<group_id>`          | Activates or deactivates a group for dispatches.             |
| `GET`    | `/schedules`                           | Lists dispatch times.                                        |
| `POST`   | `/schedules`                           | Creates a dispatch time.                                     |
| `PATCH`  | `/schedules/<schedule_id>`             | Updates time, days, timezone or active flag.                 |
| `DELETE` | `/schedules/<schedule_id>`             | Deletes a dispatch time.                                     |
| `GET`    | `/dispatch-settings`                   | Returns delays between groups and daily limit.               |
| `PATCH`  | `/dispatch-settings`                   | Updates delays between groups and daily limit.               |
| `GET`    | `/dispatch-runs`                       | Lists executed schedules with a per-status summary.          |
| `GET`    | `/dispatch-runs/<run_id>`              | Returns a run with the result for each group.                |
| `GET`    | `/dispatches`                          | Lists sends, optionally filtered by `status`.                |
| `POST`   | `/dispatches/<dispatch_id>/retry`      | Retries a failed or skipped send.                            |
| `POST`   | `/webhooks/evolution`                  | Evolution API webhook for QR code and connection (internal). |

All endpoints except `/auth/*` and `/webhooks/evolution` require a JWT Bearer token in the `Authorization` header.

### Core Endpoints

#### Create Offer Endpoint

- **URL**: `/offers`
- **Method**: `POST`
- **Description**: Creates an offer in `draft` status. The discount is calculated by the database.
- **Security**: Requires JWT Bearer token in Authorization header.

##### Request Body Create Offer:

- **Content-Type**: `application/json`
- **Request Fields**:
  - `product_name`: Product name (required).
    - Type: `String`, 2 to 200 characters
    - **Example**: `JBL Tune 520BT Headphones`
  - `url`: Product link (required).
    - Type: `String`, must start with `http://` or `https://`
    - **Example**: `https://amzn.to/abc`
  - `original_price_cents`: Original price in cents (required).
    - Type: `Integer`
    - **Example**: `29990`
  - `price_cents`: Promotional price in cents, not greater than the original (required).
    - Type: `Integer`
    - **Example**: `17990`
  - `message`: Message template (optional). Uses the default template when empty.
    - Type: `String`, up to 4000 characters
    - **Placeholders**: `{product_name}`, `{price}`, `{original_price}`, `{discount}`, `{url}`
    - **Example**: `🔥 *{product_name}* for *R$ {price}* ({discount}% OFF) {url}`

###### Example Request Create Offer

```sh
curl -X POST "http://127.0.0.1:5000/offers" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {token}" \
-d '{"product_name": "JBL Tune 520BT Headphones", "url": "https://amzn.to/abc", "original_price_cents": 29990, "price_cents": 17990}'
```

#### Upload Offer Image Endpoint

- **URL**: `/offers/<offer_id>/image`
- **Method**: `PUT`
- **Description**: Uploads or replaces the offer image. The previous image is deleted from storage.
- **Security**: Requires JWT Bearer token in Authorization header.

##### Request Body Upload Offer Image:

- **Content-Type**: `multipart/form-data`
- **Request Fields**:
  - `image`: Image file (required).
    - Type: `File`
    - **Supported Formats**: `jpeg`, `png`, `webp`, up to 5 MB

###### Example Request Upload Offer Image

```sh
curl -X PUT "http://127.0.0.1:5000/offers/{offer_id}/image" \
-H "Authorization: Bearer {token}" \
-F "image=@product.jpg"
```

#### Connect WhatsApp Endpoint

- **URL**: `/whatsapp/connect`
- **Method**: `POST`
- **Description**: Creates the user's Evolution API instance, or generates a new QR code when it already exists. The response contains the QR code as a base64 image. Scan it in WhatsApp > Linked devices; the connection status arrives through the webhook and can be read with `GET /whatsapp`.
- **Security**: Requires JWT Bearer token in Authorization header.

###### Example Request Connect WhatsApp

```sh
curl -X POST "http://127.0.0.1:5000/whatsapp/connect" \
-H "Authorization: Bearer {token}"
```

#### Update Group Endpoint

- **URL**: `/whatsapp/groups/<group_id>`
- **Method**: `PATCH`
- **Description**: Activates or deactivates a group for scheduled dispatches. Groups where only admins can send and the number is not an admin cannot be activated.
- **Security**: Requires JWT Bearer token in Authorization header.

##### Request Body Update Group:

- **Content-Type**: `application/json`
- **Request Fields**:
  - `active`: Whether the group receives the offers (required).
    - Type: `Boolean`
    - **Example**: `true`

###### Example Request Update Group

```sh
curl -X PATCH "http://127.0.0.1:5000/whatsapp/groups/{group_id}" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {token}" \
-d '{"active": true}'
```

#### Create Schedule Endpoint

- **URL**: `/schedules`
- **Method**: `POST`
- **Description**: Creates a dispatch time. At each time the worker sends the next queued offer.
- **Security**: Requires JWT Bearer token in Authorization header.

##### Request Body Create Schedule:

- **Content-Type**: `application/json`
- **Request Fields**:
  - `send_time`: Time in 24-hour format (required).
    - Type: `String`, `HH:MM`
    - **Example**: `09:00`
  - `days_of_week`: Days when the schedule runs (optional, every day by default).
    - Type: `Array<Integer>`, `1` (Monday) to `7` (Sunday)
    - **Example**: `[1, 2, 3, 4, 5]`
  - `timezone`: IANA timezone (optional).
    - Type: `String`
    - **Example**: `America/Sao_Paulo`
  - `active`: Whether the schedule is enabled (optional).
    - Type: `Boolean`
    - **Example**: `true`

###### Example Request Create Schedule

```sh
curl -X POST "http://127.0.0.1:5000/schedules" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {token}" \
-d '{"send_time": "09:00", "days_of_week": [1, 2, 3, 4, 5]}'
```

#### Queue Offer Endpoint

- **URL**: `/offers/<offer_id>/queue`
- **Method**: `POST`
- **Description**: Adds the offer to the end of the queue. Sent offers can be queued again.
- **Security**: Requires JWT Bearer token in Authorization header.

###### Example Request Queue Offer

```sh
curl -X POST "http://127.0.0.1:5000/offers/{offer_id}/queue" \
-H "Authorization: Bearer {token}"
```

### Example Use Case

#### From Offer to Scheduled Dispatch

```sh
API=http://127.0.0.1:5000

TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Str0ng#Pass"}' | jq -r .access_token)

curl -s -X POST "$API/whatsapp/connect" -H "Authorization: Bearer $TOKEN" | jq -r .qrcode

curl -s -X POST "$API/whatsapp/groups/sync" -H "Authorization: Bearer $TOKEN" | jq '.groups[] | {id, name, can_send}'

curl -s -X PATCH "$API/whatsapp/groups/{group_id}" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"active": true}'

OFFER=$(curl -s -X POST "$API/offers" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"product_name": "JBL Tune 520BT Headphones", "url": "https://amzn.to/abc", "original_price_cents": 29990, "price_cents": 17990}' | jq -r .offer.id)

curl -s -X PUT "$API/offers/$OFFER/image" -H "Authorization: Bearer $TOKEN" -F "image=@product.jpg"

curl -s -X POST "$API/offers/$OFFER/queue" -H "Authorization: Bearer $TOKEN"

curl -s -X POST "$API/schedules" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"send_time": "09:00"}'

curl -s "$API/dispatch-runs" -H "Authorization: Bearer $TOKEN" | jq
```

The message sent to each active group looks like this:

```plaintext
🔥 *JBL Tune 520BT Headphones*

From ~R$ 299,90~ to *R$ 179,90*
40% OFF

🛒 https://amzn.to/abc
```

## How Dispatching Works

1. Every 30 seconds the worker looks for active schedules whose time has arrived, in each schedule's timezone. Times missed by up to 10 minutes, for example while the worker was restarting, are still executed.
2. Each schedule runs at most once per time slot, guaranteed by a unique constraint in the database, and a Redis lock keeps a single worker active.
3. The run takes the oldest queued offer and sends it to every active group, one at a time, waiting a random delay between `min_delay_seconds` and `max_delay_seconds`.
4. Failed sends are retried once. If the number disconnects, the run stops and the remaining groups are marked as failed.
5. When the daily limit is reached, the remaining groups are skipped until the next day.
6. The offer becomes `sent` when at least one group receives it. Empty queues and runs without active groups are recorded as `skipped`.

## License

This project is licensed under the terms of the [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](./LICENSE) file for details.
