{{/*
Expand the name of the chart.
*/}}
{{- define "migrator-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fully qualified app name.
We truncate at 63 chars because some Kubernetes resources are limited to this.
*/}}
{{- define "migrator-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label value.
*/}}
{{- define "migrator-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels for all resources.
*/}}
{{- define "migrator-platform.labels" -}}
helm.sh/chart: {{ include "migrator-platform.chart" . }}
{{ include "migrator-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: migrator-platform
{{- end }}

{{/*
Selector labels for the API deployment.
*/}}
{{- define "migrator-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "migrator-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Labels for a specific component (pass component name as arg).
Usage: {{ include "migrator-platform.componentLabels" (dict "root" . "component" "api") }}
*/}}
{{- define "migrator-platform.componentLabels" -}}
{{ include "migrator-platform.labels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Selector labels for a specific component.
Usage: {{ include "migrator-platform.componentSelectorLabels" (dict "root" . "component" "api") }}
*/}}
{{- define "migrator-platform.componentSelectorLabels" -}}
{{ include "migrator-platform.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "migrator-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "migrator-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Application image reference.
*/}}
{{- define "migrator-platform.image" -}}
{{- $registry := .Values.image.registry -}}
{{- if .Values.global.imageRegistry -}}
  {{- $registry = .Values.global.imageRegistry -}}
{{- end -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .Values.image.repository .Values.image.tag }}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end -}}
{{- end }}

{{/*
Qdrant image reference.
*/}}
{{- define "migrator-platform.qdrantImage" -}}
{{- $registry := .Values.qdrant.image.registry -}}
{{- if .Values.global.imageRegistry -}}
  {{- $registry = .Values.global.imageRegistry -}}
{{- end -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .Values.qdrant.image.repository .Values.qdrant.image.tag }}
{{- else -}}
{{- printf "%s:%s" .Values.qdrant.image.repository .Values.qdrant.image.tag }}
{{- end -}}
{{- end }}

{{/*
PostgreSQL host — either the subchart service or an external host.
*/}}
{{- define "migrator-platform.postgresHost" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" .Release.Name }}
{{- else -}}
{{- .Values.externalDatabase.host }}
{{- end -}}
{{- end }}

{{/*
Redis host — either the subchart service or an external host.
*/}}
{{- define "migrator-platform.redisHost" -}}
{{- if .Values.redis.enabled -}}
{{- printf "%s-redis-master" .Release.Name }}
{{- else -}}
{{- .Values.externalRedis.host }}
{{- end -}}
{{- end }}

{{/*
Full DATABASE_URL connection string.
*/}}
{{- define "migrator-platform.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.postgresql.auth.username }}:$(POSTGRES_PASSWORD)@{{ include "migrator-platform.postgresHost" . }}:5432/{{ .Values.postgresql.auth.database }}
{{- end }}

{{/*
Redis URL.
*/}}
{{- define "migrator-platform.redisUrl" -}}
redis://{{ include "migrator-platform.redisHost" . }}:6379/0
{{- end }}

{{/*
Celery broker URL (Redis DB 1).
*/}}
{{- define "migrator-platform.celeryBrokerUrl" -}}
redis://{{ include "migrator-platform.redisHost" . }}:6379/1
{{- end }}
