FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev=false

COPY . .

EXPOSE 3001

ENV NEXT_TELEMETRY_DISABLED=1

CMD ["npm", "run", "dev"]
