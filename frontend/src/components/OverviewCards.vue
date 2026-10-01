<script setup lang="ts">
import type { Overview } from '../types/domain'
defineProps<{ overview: Overview }>()
</script>
<template><div class="stat-grid"><div v-for="(label,index) in overview.chart.labels" :key="label" class="stat-card"><span>{{ label }}</span><strong>{{ overview.chart.values[index] }}</strong></div></div></template>
