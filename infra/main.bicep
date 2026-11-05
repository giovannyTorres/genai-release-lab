@description('Existing Container Apps environment; no resources are deployed by this repository task.')
param environmentName string
param location string = resourceGroup().location
param apiImage string
param webImage string
@secure()
param databaseUrl string
@secure()
param liveUsersJson string = ''
@secure()
param openaiKey string = ''
@secure()
param geminiKey string = ''
param mode string = 'DEMO'
param publicOrigin string
param endpointAllowedHosts string = ''

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

var sharedEnv = [
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'APP_MODE', value: mode }
  { name: 'PUBLIC_ORIGIN', value: publicOrigin }
  { name: 'COOKIE_SECURE', value: 'true' }
  { name: 'LIVE_USERS_JSON', secretRef: 'live-users' }
  { name: 'OPENAI_API_KEY', secretRef: 'openai-key' }
  { name: 'GEMINI_API_KEY', secretRef: 'gemini-key' }
  { name: 'ENDPOINT_ALLOWED_HOSTS', value: endpointAllowedHosts }
]
var sharedSecrets = [
  { name: 'database-url', value: databaseUrl }
  { name: 'live-users', value: liveUsersJson }
  { name: 'openai-key', value: openaiKey }
  { name: 'gemini-key', value: geminiKey }
]
resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'release-api'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: sharedSecrets
      ingress: { external: false, targetPort: 8103, transport: 'http' }
    }
    template: {
      containers: [{
        name: 'api'
        image: apiImage
        env: sharedEnv
        command: ['sh', '-c', 'alembic upgrade head && python -m release_lab.seed && uvicorn release_lab.main:app --host 0.0.0.0 --port 8103']
        resources: { cpu: json('0.5'), memory: '1Gi' }
        probes: [{ type: 'Readiness', httpGet: { path: '/api/health', port: 8103 }, initialDelaySeconds: 10, periodSeconds: 10 }]
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}
resource worker 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'release-worker'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: { activeRevisionsMode: 'Single', secrets: sharedSecrets }
    template: {
      containers: [{
        name: 'worker'
        image: apiImage
        command: ['python', 'services/worker/main.py']
        env: sharedEnv
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [api]
}
resource web 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'release-web'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: { ingress: { external: true, targetPort: 3103, transport: 'http', allowInsecure: false } }
    template: {
      containers: [{
        name: 'web'
        image: webImage
        env: [{ name: 'PORT', value: '3103' }, { name: 'API_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }]
        resources: { cpu: json('0.5'), memory: '1Gi' }
        probes: [{ type: 'Readiness', httpGet: { path: '/', port: 3103 }, initialDelaySeconds: 10 }]
      }]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}
output website string = 'https://${web.properties.configuration.ingress.fqdn}'
