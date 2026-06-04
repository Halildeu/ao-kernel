{{/*
ao-kernel helm helpers (V5 Epic 4 E-4-1 skeleton).
Standard naming + label helpers; no business logic; no secret materialization.
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "ao-kernel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ao-kernel.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ao-kernel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "ao-kernel.labels" -}}
helm.sh/chart: {{ include "ao-kernel.chart" . }}
{{ include "ao-kernel.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
ao-kernel.dev/lifecycle: beta-skeleton
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "ao-kernel.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ao-kernel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use.
*/}}
{{- define "ao-kernel.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "ao-kernel.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
