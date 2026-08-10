{{/*
Expand the name of the chart.
*/}}
{{- define "quantum-fintek.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Full name: release-chart, capped at 63 chars.
*/}}
{{- define "quantum-fintek.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "quantum-fintek.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Selector labels for a given component.
Usage: {{ include "quantum-fintek.selectorLabels" (dict "root" . "component" "api") }}
*/}}
{{- define "quantum-fintek.selectorLabels" -}}
app.kubernetes.io/name: {{ include "quantum-fintek.name" .root }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Image reference: registry/repository:tag
*/}}
{{- define "quantum-fintek.image" -}}
{{- $reg := .root.Values.global.imageRegistry -}}
{{- if $reg -}}{{ $reg }}/{{ .image.repository }}:{{ .image.tag }}
{{- else -}}{{ .image.repository }}:{{ .image.tag }}
{{- end -}}
{{- end }}
