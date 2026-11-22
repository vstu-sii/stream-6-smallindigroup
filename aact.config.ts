import type { AactConfig } from "aact";

const config: AactConfig = {
  source: { type: "plantuml", path: "./docs/architecture/container.puml" },
  rules: {
    acl: true,
    acyclic: true,
    apiGateway: true,
    crud: true,
    dbPerService: true,
    cohesion: true,
    stableDependencies: true,
    commonReuse: true,
  },
};

export default config;
