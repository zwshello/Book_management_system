<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Overview } from '../types/domain'
const props = defineProps<{ overview: Overview }>()
echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])
const element = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined
function render() { chart?.setOption({ tooltip: { trigger: 'axis' }, grid: { top: 25, left: 52, right: 20, bottom: 60 }, xAxis: { type: 'category', data: props.overview.chart.labels, axisLabel: { interval: 0, rotate: 14 } }, yAxis: { type: 'value', minInterval: 1 }, series: [{ name: '数量', type: 'bar', data: props.overview.chart.values, barMaxWidth: 58, itemStyle: { color: '#2c78af', borderRadius: [5, 5, 0, 0] } }] }) }
function resize() { chart?.resize() }
onMounted(() => { if (element.value) { chart = echarts.init(element.value); render(); window.addEventListener('resize', resize) } })
watch(() => props.overview, render, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>
<template><div ref="element" style="width:100%;height:360px" role="img" aria-label="用户、图书及借阅数量柱状图" /></template>
