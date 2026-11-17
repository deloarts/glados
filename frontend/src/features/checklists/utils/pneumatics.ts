import { annex, article, buildChecklist, clauses, intro, item, machinery, part, section, sub, table } from './build'
import type { Reference } from './types'

/**
 * Inspection checklist for the pneumatic equipment of machines, based on
 * ISO 4414:2010 with the documentation, risk reduction and information for
 * use requirements of ISO 12100:2010. Clause numbers of ISO 4414 follow the
 * 2010 edition.
 */

const p = (...list: string[]): Reference[] => clauses('iso4414', ...list)
const risk = (...list: string[]): Reference[] => clauses('iso12100', ...list)
const estop = (...list: string[]): Reference[] => clauses('iso13850', ...list)
const symbols = (...list: string[]): Reference[] => clauses('iso1219_2', ...list)

export const PNEUMATICS = buildChecklist('pneumatics', [
  part('documentation', [
    section('assessment', [
      item('documents'),
      sub('circuitFunctions'),
      item('typeCStandard', [intro('iso4414'), intro('iso12100')]),
      sub('typeCRequirements', [intro('iso4414')]),
      item('riskAssessment', risk('5')),
    ]),
    section('circuit', [
      item('iso1219', p('7.2')),
      sub('layout', symbols('4.3.1')),
      sub('symbols', [...symbols('4.4.1'), table('iec81346_2', '1'), table('iec81346_2', '2')]),
      sub('restPosition', symbols('4.4.2')),
      sub('lineColours'),
      sub('assemblies', symbols('4.3.4')),
      sub('crossDesignations', p('7.4.4.2')),
      sub('portMarking', p('7.4.3')),
      sub('sheetTransitions', symbols('4.3.7')),
      item('partsList', [...symbols('7'), ...p('7.4.2')]),
      item('supplementary', p('7.2', '7.3')),
      item('unexpectedStart', p('5.2.8', '5.2.10'), { hint: true }),
      item('safePositionValves', p('5.4.6.9')),
      sub('safePositionMeans', p('5.4.6.9')),
      item('manualOverride', p('5.4.3.4.2.4')),
      item('overpressure', p('5.2.2')),
      item('pressureLoss', p('5.2.2.4')),
      item('switching', p('5.2.7')),
      sub('failureReturn', p('5.2.7')),
      sub('fluctuations', p('5.2.2', '5.2.7', '5.4.6.11')),
      sub('smoothMotion', p('5.2.3')),
      item('pressureSurges', p('5.2.2.3')),
      item('testPoints', p('7.3.1', '7.4.3')),
      item('sequence', p('5.4.6.13')),
      item('externalForces', p('5.2.2')),
    ]),
    section('sizing', [
      item('designData', p('5.2', '5.4.4.3.2', '5.4.5', '5.4.6.4')),
      item('componentRatings', p('5.2', '5.4.4.3.2', '5.4.5', '5.4.6.4'), { hint: true }),
      item('cylinderSizing', p('5.2.1', '5.4.2.1')),
      sub('cylinderFasteners', p('5.4.2.5')),
      item('valveMisassembly', p('5.4.3.2')),
    ]),
    section('airTreatment', [
      item('contaminants', p('5.4.4.2')),
      item('filtration', p('5.4.4.2')),
      item('filterDegradation', p('5.4.4.2')),
    ]),
    section('emergencyStop', [
      item('equipped', [...p('5.4.6.15'), ...risk('6.3.5.2')]),
      item('devices', estop('4.4.1'), { hint: true }),
      item('effect', estop('4.1.4', '4.1.5')),
      item('valves', [...p('5.4.6.9'), ...estop('4.4.3')], { see: ['emergencyStop.effect'] }),
      item('allModes', estop('4.1.1')),
      item('servoSuitable', p('5.4.6.9', '5.4.6.10'), { see: ['emergencyStop.valves'] }),
      sub('additionalValves', p('5.4.6.9')),
    ]),
    section('vesselDesign', [
      item('data'),
      sub('directive', [article('ped', '1'), article('spvd', '1')]),
      sub('category', [article('ped', '13')]),
      sub('certificates', [annex('ped', 'III'), annex('ped', 'IV')]),
      sub('inspectionBeforeUse'),
      sub('safetyDevices', [annex('ped', 'I', '7.3')]),
      item('switchedOff', [...p('5.4.10'), ...risk('6.2.10')]),
      sub('holdPressure', p('5.4.10')),
    ]),
    section('servoValves', [
      item('controlHazard', [...p('5.4.6.10'), ...clauses('ifaValves', '4.2.1.1')], { hint: true }),
      item('unintendedMotion', p('5.4.6.10'), { hint: true, see: ['servoValves.controlHazard'] }),
      item('filtration', p('5.4.4.2')),
    ]),
  ]),
  part('machine', [
    section('marking', [
      item('positionMarks', p('7.4', '7.4.2.1', '7.4.5')),
      item('componentData', [...p('7.4.1.1', '7.4.2.2'), ...clauses('iso1219_1')]),
      item('stackOrder', p('7.4.1.1')),
      item('vesselMarking', [...clauses('en286_1'), article('spvd', '1')]),
      item('valveOperators', p('7.4.4.1')),
      item('testDrainPoints', p('7.3.1 e)', '7.4.3.1')),
      item('vesselWarning', p('5.4.10')),
      item('vesselMaintenanceNote', p('5.4.10')),
      item('interchangeableLines', [...machinery('1.5.4'), ...p('5.4.5.3.2', '7.4.3.2')], {
        see: ['piping.wrongConnection'],
      }),
    ]),
    section('assembly', [
      item('conformsToDiagram', p('6')),
      item('mountingPosition', p('5.2.1.2', '5.4.3.2')),
      item('cylinderFasteners', p('5.4.2.5'), { see: ['sizing.cylinderFasteners'] }),
      sub('fastenersSecured', p('5.4.2.4')),
      item('mechanicalValves', p('5.4.3.4.1')),
      item('intensification', p('5.2.2'), { see: ['circuit.overpressure', 'circuit.externalForces'] }),
      sub('backPressure', p('5.4.3.2')),
      item('bowlGuards', p('5.4.4.5.1')),
    ]),
    section('piping', [
      item('pipeSupport', p('5.4.5.5')),
      item('supportDamage', p('5.4.5.5.2')),
      item('componentsOnPipes', p('5.4.5.2.2')),
      item('notAStep', p('5.4.5.2.1')),
      item('wrongConnection', [...p('5.4.5.3.2', '7.4.3.2'), ...machinery('1.5.4')]),
      sub('wrongConnectionMarking', p('7.4.3.2')),
      item('protectedRouting', p('5.4.5.3.1')),
      item('hoseMarking', p('7.4.3.3')),
      item('tubeMarking', p('7.4.3.4')),
      item('notReused', p('5.4.5.9.1 a)')),
      item('serviceLife', p('5.4.5.9.1 b)')),
      item('hoseInstallation', p('5.4.5.9.2', '5.2.1.1', '5.3.3')),
      item('whipProtection', p('5.4.5.11')),
      item('quickCouplings'),
    ]),
    section('exhaust', [
      item('exhaustAir', p('5.2.2.5', '5.2.12', '5.2.4', '5.2.5', '5.4.8', '5.4.3.6')),
      item('singleActing', p('5.4.2.9')),
      item('testPoints', p('5.3.2.2', '7.3.1 e)'), { see: ['circuit.testPoints'] }),
    ]),
    section('maintenance', [
      item('access', [...p('5.3.1 m)', '5.3.2'), ...machinery('1.6')]),
      item('residualPressure', p('5.2.8')),
      item('removal', p('5.3.2.1')),
    ]),
    section('electrical', [
      item('solenoidVoltage', p('5.4.3.4.2.3')),
      item('solenoidProtection', [...clauses('iec60204_1', '11.3'), ...p('5.4.3.4.2.1')]),
      item('terminalBoxes', p('5.4.3.4.2.2')),
      item('coversSecured', p('5.4.3.4.2.2')),
    ]),
    section('energySupply', [
      item('switching', p('5.2.7'), { see: ['circuit.switching', 'circuit.failureReturn'] }),
      item('indicators', p('5.4.6.11'), { see: ['circuit.fluctuations'] }),
    ]),
    section('actuators', [
      item('design', [...risk('6.2.8'), ...p('7.4.4.1', '5.4.6.6', '5.4.6.14.1', '5.4.3.4.2.4'), ...machinery('1.2.2')]),
      item('multiFunction', risk('6.2.8')),
      item('manualOverride', p('5.4.3.4.2.4'), { see: ['circuit.manualOverride'] }),
    ]),
    section('indicators', [
      item('visible', [...machinery('1.7', '1.2.2'), ...p('5.4.6.11')]),
      sub('gauges', p('5.4.6.11')),
    ]),
    section('adjustments', [item('tamperProof', p('5.4.6.3', '5.4.6.5'))]),
    section('cylinders', [item('endStops', p('5.4.2.7')), item('rodProtection', p('5.4.2.8'))]),
    section('fire', [item('hoseFire', p('5.3.1 j)', '5.4.5.1.1')), item('lubricatedExhaust')]),
    section('rescue', [
      item('rescuePossible', [...risk('6.3.5.3', '6.4'), ...p('5.4.3.4.2.4')]),
      item('rescueNotes', [...machinery('1.7.2'), ...risk('6.4.4')]),
    ]),
    section('vesselCheck', [
      item('shutdown', [...risk('6.2.10', '6.3.5.4'), ...p('5.2.8', '5.4.10')]),
      sub('warningSign', p('5.4.10'), { see: ['marking.vesselWarning'] }),
      item('remoteLines', [...machinery('1.7.2'), ...risk('6.4.4')], { see: ['marking.vesselMaintenanceNote'] }),
      item('noModifications'),
    ]),
    section('tests', [
      item('functions', p('6')),
      item('safetyDevices', p('6')),
      sub('emergencyStop', p('6'), {
        see: ['emergencyStop.devices', 'emergencyStop.effect', 'emergencyStop.allModes', 'emergencyStop.servoSuitable'],
      }),
      sub('noNewHazards', [...risk('6.3.5.2'), ...machinery('1.2.4')]),
      sub('restart', machinery('1.2.4')),
      item('pressureTest', p('6')),
      item('speedLimits', p('5.2.1.1')),
      item('noBending', p('5.4.2.1')),
    ]),
  ]),
  part('instructions', [
    section('manual', [
      item('contents', [...p('5.3.1', '7.2'), ...risk('6.4.5.1 c)')]),
      item('transport', [...risk('6.4.5.1 a)'), ...p('5.3.4')]),
      item('commissioning', risk('6.4.5.1 b)')),
      item('lubricants', [...p('5.4.4.3', '5.4.4.4', '5.4.4.2.5', '7.2 g)'), ...risk('6.4.5.1 b)')]),
      sub('safetyDataSheet', p('5.4.4.3')),
      item('maintenance', [...p('7.3', '5.4.5.9'), ...risk('6.4.5.1 d)', '6.4.5.1 e)')]),
      item('emergencies', risk('6.4.5.1 g)', '6.3.5.2', '6.3.5.3')),
    ]),
  ]),
])
