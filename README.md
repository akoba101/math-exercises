# Math Exercises

Practice fraction arithmetic, check answers, and download printable worksheets.

## Run with Docker

From the repository directory, with Docker configured for Linux containers:

    docker build -t math-exercises .
    docker run --rm -p 127.0.0.1:8000:8000 math-exercises

Open http://localhost:8000. Press Ctrl+C to stop the container.
If port 8000 is in use, publish 127.0.0.1:8080:8000 and open http://localhost:8080.
