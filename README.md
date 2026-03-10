# Cloud Manager

## What's This About?

Cloud Manager is a full-stack app that helps you:
- Manage your cloud resources (like EC2, S3, etc.) using simple prompts in natural language with the help of AI
- Keep track of everything with execution logs so you know whats pumping up your bill
- Get a real-time view of your cloud setup

The system was designed to be simple to deploy while still supporting practical cloud management workflows. The frontend is built with **Next.js**, providing a responsive interface for interacting with the platform, while the backend uses **FastAPI** to handle API requests, authentication, and application logic.

At the core of the system is a **Large Language Model (LLM)** deployed using **Ollama** that interprets natural language prompts and converts them into structured infrastructure operations. These operations are executed through a **Model Context Protocol (MCP) server**, which defines the available tools, their schemas, and the execution logic for managing cloud resources. By centralizing tool definitions within MCP, the architecture ensures modularity and extensibility, allowing new capabilities to be added without modifying the LLM service.

All components, including the frontend, backend, LLM service, MCP server, and database, are containerized using **Docker**, enabling consistent deployment and simplified setup.
<!-- 
## Video Demo

Check out this quick demo to see it in action: [Watch the Demo](https://www.youtube.com/watch?v=dQw4w9WgXcQ) -->

## How It's Built

Here's the breakdown of what's under the hood:

### Services

| Service       | What It Does                          | Runs On |
|---------------|---------------------------------------|---------|
| **Frontend**  | The web app (Next.js + Tailwind CSS)  | Port 3000 |
| **API Server**| Handles authentication, resources, etc. | Port 8000 |
| **LLM Service**| AI-powered prompt parsing            | Port 8001 |
| **MCP Server**| Manages cloud tools and integrations  | Port 8002 |
| **Database**  | PostgreSQL for storing data           | Port 5432 |
| **Cache**     | Redis for caching and sessions        | Port 6379 |

### Tech Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** FastAPI, SQLAlchemy, Pydantic, JWT
- **Data:** PostgreSQL, Redis
- **Infra:** Docker, Python

## Why I Did It This Way

I aimed to create a solution that is both user-friendly and robust enough to address complex, real-world scenarios. To achieve this, I utilized Next.js for the frontend, leveraging its server-side rendering capabilities and modern development features. For the backend, I chose FastAPI due to its high performance, clean design, and support for asynchronous operations. Additionally, I integrated a Large Language Model (LLM) service to enable intelligent prompt parsing and execution. The Model Context Protocol (MCP) server plays a pivotal role in managing cloud tools and ensuring seamless integration across services. The entire system is containerized with Docker, ensuring consistent deployment and simplified setup across environments.

## How to Get Started

### Prerequisites

You'll need:
- Docker Desktop (v2.0+)
- A good system (Mine is an i7 with 16GB RAM, and idk if it will run on something less powerful, but give it a try!)
- A good GPU is recommended for the LLM service, but it _might_ run on CPU _(just slower)_
- Optional: AWS credentials if you want to use real AWS resources, otherwise it just returns mock data

### Steps

1. Clone the repo and set up your environment:
   ```bash
   git clone https://github.com/Nalin-Angrish/CM.git
   cd CM
   cp .env.example .env
   ```

2. Edit the `.env` file with your details (like database credentials, JWT secret, etc.).

3. Start the services:
   ```bash
   docker-compose up --build -d
   ```

4. Pull the latest LLM model (if you have Ollama installed):
   ```bash
   docker-compose exec ollama ollama pull llama3.1:8b
   ```
   This only needs to be done once, and it will be cached for future runs. If you delete the ollama volume for any reason whatsoever, you'll need to pull the model again.

5. Open your browser:
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

That's it! You're up and running.

## Project Structure

Here's how everything is organized:

```
.
├── frontend/                # Next.js frontend
├── api-server/              # FastAPI backend
├── llm-service/             # LLM integration
├── mcp-server/              # Cloud tools server
├── database/                # Database setup
├── docker-compose.yml       # Docker Compose config
└── README.md                # This file
```

## Troubleshooting

If something doesn't work, here are a few tips:

- **Services won't start:**
  ```bash
  docker-compose down -v
  docker-compose up --build
  ```

- **Database issues:** Check your `.env` file and make sure the database credentials are correct.

- **Ports in use:** Change the port mappings in `docker-compose.yml`.

## What's Next?

Here are some things I'm planning to add:
- Better filtering and search for resources
- Real-time dashboards
- Multi-region AWS support
- Role-based access control
- Exportable execution logs

If you have ideas or suggestions, feel free to share!

## License

I don't think anybody cares but this project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.