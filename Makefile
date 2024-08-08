all: prep
	@docker compose -f ./srcs/docker-compose.yml up -d --build

down:
	@docker compose -f ./srcs/docker-compose.yml down

re: prep
	@docker compose -f srcs/docker-compose.yml up -d --build

clean:
	@if [ -n "$$(docker ps -qa)" ]; then \
		docker stop $$(docker ps -qa); \
		docker rm $$(docker ps -qa); \
	fi
	@if [ -n "$$(docker images -qa)" ]; then \
		docker rmi -f $$(docker images -qa); \
	fi
	@if [ -n "$$(docker volume ls -q)" ]; then \
		docker volume rm $$(docker volume ls -q); \
	fi
	@docker network ls | tail -n +2 | awk '$$2 !~ /bridge|none|host/' | awk '{ print $$1 }' | xargs -r -I {} docker network rm {}

prep:
	@if [ ! -d "/home/$$USER/shared_data" ]; then \
		mkdir -p /home/$$USER/shared_data; \
	fi

.PHONY: all re down clean prep
