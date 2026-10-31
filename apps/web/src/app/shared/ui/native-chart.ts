import { Component, effect, inject, Input, OnChanges } from '@angular/core';
import { PreferencesService } from '../../core/ui/preferences.service';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import type { EChartsCoreOption } from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, AriaComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, SVGRenderer]);

export interface ChartDatum { label: string; value: number }
export type ChartKind = 'trend' | 'bars' | 'donut';

/** Native ECharts graphs. No fabricated values; data comes from API-bound parents. */
@Component({
  selector: 'tr-native-chart', standalone: true, imports: [NgxEchartsDirective],
  providers: [provideEchartsCore({echarts})],
  template: `
    <div class="chart-frame">
    <div echarts [options]="options" [autoResize]="true" [initOpts]="chartInit"
      [style.height.px]="height" class="w-full" role="img" [attr.aria-label]="description"></div>
    @if(kind==='donut'){<div class="chart-total" aria-hidden="true"><strong>{{total()}}</strong><span>{{totalLabel}}</span></div>}
    </div>
    <p class="sr-only">{{description}} :
       @for(item of data;track $index){ {{item.label}} : {{item.value}}. }
    </p>
  `,
  styles: [`.chart-frame{position:relative}.chart-total{position:absolute;top:42%;left:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;gap:4px;pointer-events:none}.chart-total strong{font-size:28px;font-weight:650;letter-spacing:-.04em;color:var(--tr-ink);font-variant-numeric:tabular-nums}.chart-total span{font-size:11px;color:var(--tr-muted)}`]
})
export class NativeChart implements OnChanges {
  @Input() data: ChartDatum[] = [];
  @Input() kind: ChartKind = 'trend';
  @Input() description = 'Graphique des données de l’organisation';
  @Input() height = 252;
  @Input() totalLabel = 'Total';
  readonly chartInit = {renderer: 'svg' as const};
  options: EChartsCoreOption = {};
  private readonly prefs = inject(PreferencesService);
  constructor() { effect(() => { this.prefs.isDark(); this.ngOnChanges(); }); }
  total(){return new Intl.NumberFormat('fr-FR').format(this.data.reduce((sum,row)=>sum+(Number.isFinite(row.value)&&row.value>=0?row.value:0),0));}

  ngOnChanges(): void {
    const rows = this.data.filter(v => !!v.label && Number.isFinite(v.value) && v.value >= 0).slice(0, 30);
    const labels = rows.map(v => v.label);
    const values = rows.map(v => v.value);
    const dark = this.prefs.isDark();
    const ink = dark ? '#aabdc7' : '#647b88';
    const blue = dark ? '#8aceca' : '#32878e';
    const line = dark ? '#2c414d' : '#e9eef1';
    const reducedMotion = typeof matchMedia!=='undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const common = { animation:!reducedMotion, animationDuration: 250, aria: {enabled: true},
      tooltip: {renderMode:'richText', trigger: this.kind==='donut' ? 'item' : 'axis', valueFormatter: (v: unknown) => String(v ?? 0)},
      textStyle: {fontFamily: 'ui-sans-serif, system-ui, sans-serif', color: ink, fontSize: 11} };
    if (this.kind === 'donut') {
      this.options = {...common, tooltip: {renderMode:'richText', trigger: 'item'},
        legend: {type:'scroll', orient:'horizontal', bottom: 0, textStyle: {color:ink}},
        series: [{type: 'pie', radius:['61%','78%'], center:['50%','42%'],
          avoidLabelOverlap:true, label:{show:false},
          emphasis:{scale:false}, itemStyle:{borderRadius:4,borderColor:dark?'#18262f':'#ffffff',borderWidth:3},
          color:[blue,'#639ec0','#91b8a9','#d5a365','#8b91b2','#c7837a'],
          data: rows.map(v => ({name:v.label,value:v.value}))}]} as EChartsCoreOption;
    } else if(this.kind === 'bars'){
      this.options = {...common, grid:{left:12,right:28,top:12,bottom:15,containLabel:true},
        xAxis:{type:'value', min:0, minInterval:1, axisLabel:{color:ink}, splitLine:{lineStyle:{color:line,type:'dashed'}}},
        yAxis:{type:'category',data:labels, inverse:true, axisLabel:{color:ink,width:90,overflow:'truncate'},axisLine:{show:false},axisTick:{show:false}},
        series:[{type:'bar',data:values,itemStyle:{color:blue,borderRadius:[0,4,4,0]},barMaxWidth:13,label:{show:true,position:'right',color:ink,fontSize:11}}]} as EChartsCoreOption;
    } else {
      this.options = {...common, grid:{left:15,right:16,top:18,bottom:28,containLabel:true},
        xAxis:{type:'category',data:labels,boundaryGap:rows.length===1,axisLabel:{color:ink,hideOverlap:true,formatter:(v:string)=>/^\d{4}-\d{2}-\d{2}$/.test(v)?v.slice(8)+'/'+v.slice(5,7):v},axisLine:{show:false},axisTick:{show:false}},
        yAxis:{type:'value',min:0,minInterval:1,axisLabel:{color:ink},splitLine:{lineStyle:{color:line,type:'dashed'}}},
        series:[rows.length===1?{type:'bar',data:values,barMaxWidth:42,itemStyle:{color:blue,borderRadius:[5,5,0,0]},label:{show:true,position:'top',color:ink}}:{type:'line',data:values,smooth:false,symbolSize:6,itemStyle:{color:blue},lineStyle:{width:2.5,color:blue},areaStyle:{color:dark?'rgba(138,206,202,.08)':'rgba(50,135,142,.07)'}}]} as EChartsCoreOption;
    }
  }
}
