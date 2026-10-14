# Final Submission

Student Name: Vemula Suman

Project Name: Production-Grade Agentic RAG Capstone

GitHub Repository:
https://github.com/suman520-git/production-grade-agentic-rag

AWS Application:
http://65.1.108.31:8502

FastAPI Swagger:
http://65.1.108.31:8000/docs

Architecture Diagram: [Architecture](architecture.md)

Database Schema: [Schema](database_schema.md)

SQL Schema: [SQL](database_schema.sql)

Evaluation Report: [Report](evaluation_report.md)

## Evaluation result

The final local evaluation run passed 50/50 questions.
This result applies to the project's fixed evaluation dataset.
AWS deployment was checked separately using document ingestion,
a cited answer, an unsupported question, and the readiness endpoint.

## Access

Enter the deployment's application API key in Streamlit.
For Swagger, use the Authorize button.

The API key is provided separately to the evaluator and is not
included in this repository.

## Deployment limitations

This capstone deployment uses public HTTP without TLS.
Use sample documents only.

The application runs on one EC2 instance.
Its public IP may change after stopping and starting the instance.
Update the submission links if that happens.

Screenshots are omitted.