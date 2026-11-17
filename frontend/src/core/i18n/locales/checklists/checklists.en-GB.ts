// Messages for checklists, merged into the en-GB locale.
export default {
  type: 'Checklist',
  types: {
    hydraulics: 'Hydraulics',
    pneumatics: 'Pneumatics',
    robotics: 'Robotics',
  },
  savedTitle: '{type} checklist, {subject}',
  savedTitlePlain: 'New checklist ({type})',
  title: 'Checklists',
  revisionLabel: 'Rev. {revision}',
  changedBadge: 'Changed',
  sectionChanges: 'Changed: {count}',
  owner: {
    personal: 'Personal',
    project: 'Project',
    product: 'Product',
  },
  status: {
    draft: 'Draft',
    done: 'Done',
    released: 'Released',
    superseded: 'Superseded',
    unsaved: 'Unsaved changes',
    releasedBy: 'Released by {name} on {date}',
    supersededOn: 'Replaced by a newer revision on {date}',
  },
  list: {
    number: 'Number',
    empty: 'No checklists yet.',
    type: 'Type',
    title: 'Title',
    owner: 'Belongs to',
    result: 'Result',
    completion: '{percent} %',
    completionHeader: 'Completion',
    findings: 'Findings',
    designation: 'Machine',
    status: 'Status',
    author: 'Created by',
    changed: 'Changed',
  },
  actions: {
    new: 'New Checklist',
    open: 'Open',
    save: 'Save',
    revise: 'New Revision',
    compare: 'Compare',
    history: 'History',
    print: 'Print',
    printBlocked: 'Save your changes before printing.',
    owner: 'Change owner',
    release: 'Release',
    done: 'Done',
  },
  releaseBlocked: {
    incomplete: 'Every item needs an answer.',
    remarks: 'Every finding needs a remark.',
    ownRevision: 'Someone other than the creator of this revision has to release it.',
  },
  dialog: {
    createTitle: 'New checklist',
    ownerTitle: 'Change owner',
    create: 'Create',
    owner: 'Belongs to',
    ownerHint: {
      personal: 'Only you (and managers) can see a personal checklist.',
      project: 'Everyone can see the checklists of a project on its Checklists tab.',
      product: 'Everyone can see the checklists of a product on its Checklists tab.',
    },
    ownerRequired: 'Choose what the checklist belongs to.',
  },
  revise: {
    title: 'New Revision',
    intro:
      'The new revision starts with the answers and remarks of revision {revision}. Revision {revision} is kept as it is.',
    reason: 'Reason for the new revision',
    reasonRequired: 'Enter a reason.',
    submit: 'Start revision',
  },
  history: {
    title: 'Revisions',
    revision: 'Revision',
    reason: 'Reason',
    firstRevision: 'First revision',
    compareWith: 'Compare with this revision',
  },
  compare: {
    title: 'Compare revisions',
    back: 'Back to the checklist',
    from: 'Compare from',
    to: 'Compare to',
    nothing: 'This is the first revision, there is nothing to compare it with.',
    findings: 'Findings: {count}',
  },
  diff: {
    none: 'The two revisions do not differ.',
    header: 'Checklist data',
    field: 'Field',
    unanswered: 'Unanswered',
    removedItems: 'Items no longer in the checklist',
    fields: {
      ownerNumber: 'Number',
      ownerCustomer: 'Customer',
      ownerProduct: 'Product',
      ownerManager: 'Designated user',
      designation: 'Designation',
      machineType: 'Type',
      placingOnMarket: 'Planned placing on the market',
      installationSite: 'Installation site',
      installationLocation: 'Installation location',
      legalBasis: 'Legal basis',
      assessedBy: 'Assessed by',
      assessedOn: 'Assessed on',
      reason: 'Reason, if not passed',
      notes: 'Notes',
    },
  },
  confirm: {
    release: {
      header: 'Release checklist',
      message:
        'Releasing signs the checklist off. It cannot be changed afterwards; changes go through a new revision.',
      accept: 'Release',
      saveFirst: 'Your unsaved changes are saved first.',
    },
    delete: {
      header: 'Delete checklist',
      message:
        'This revision is deleted for good. The revision before it, if there is one, becomes the latest again.',
      accept: 'Delete',
    },
  },
  toasts: {
    saved: 'Checklist saved.',
    release: 'Checklist released.',
    delete: 'Checklist deleted.',
    revised: 'Revision {revision} started.',
  },
  errors: {
    unknown: 'Something went wrong. Please try again.',
    notFound: 'The checklist could not be found, or you may not open it.',
    loadList: 'The checklists could not be loaded.',
    unknownType: 'This checklist has a type this version of Glados does not know.',
  },
  notices: {
    dropped:
      'This checklist type has changed since it was saved. Answers and remarks for items it no longer has are left out when you save ({count}).',
    notLatest: 'This is not the latest revision, revision {revision} is newer.',
    openLatest: 'Open the latest revision',
    changesSince:
      'Items changed since revision {revision}: {count}. They are marked, and the "Changed" filter shows only them.',
  },
  info: {
    typeTitle: '{type} Checklist',
    created: 'Created by {name} on {date}',
    changed: 'Changed on {date}',
  },
  report: {
    revision: 'Revision',
    owner: 'Belongs to',
    createdBy: 'Created by',
    status: 'Status',
    draft: 'Draft, not released',
    number: 'No.',
    position: 'Item',
    requirement: 'Requirement',
    answer: 'Answer',
    hintsOption: 'Add the explanations of the items',
  },
  header: {
    title: 'Checklist data',
    owner: {
      project: 'Project',
      product: 'Product',
      customer: 'Customer',
      manager: 'Designated user',
      personal: 'A personal checklist, it belongs to no project or product.',
    },
    designation: 'Designation',
    machineType: 'Type',
    placingOnMarket: 'Planned placing on the market',
    installationSite: 'Installation site',
    installationLocation: 'Installation location',
    legalBasis: 'Legal basis',
    machineDataHint: 'The machine data comes from the product. Change it on the product page.',
    legalBasisOutdated:
      'Directive 2006/42/EC no longer applies to machinery placed on the market from 2027-01-20. Regulation (EU) 2023/1230 applies.',
    confirmationTitle: 'Confirmation',
    confirmation:
      'All participants named below have confirmed the assessment and checked it for correctness. All measures listed to avoid hazards are complied with to improve safety at the workplace.',
    assessedBy: 'Assessed by',
    assessedOn: 'Assessed on',
    checkedBy: 'Checked and released by',
    notReleased: 'Not released yet',
    reason: 'Reason, if not passed',
    notes: 'Notes',
  },
  legalBases: {
    directive: 'Directive 2006/42/EC',
    regulation: 'Regulation (EU) 2023/1230',
  },
  answers: {
    na: 'n/a',
    yes: 'Yes',
    no: 'No',
    defect: 'Defect',
  },
  answerTitles: {
    na: 'Not applicable',
    yes: 'Fulfilled',
    no: 'Not fulfilled',
    defect: 'Defect found',
  },
  answerGroup: 'Answer to {position}',
  verdicts: {
    passed: 'Passed',
    open: 'Open',
    failed: 'Failed',
  },
  verdictHints: {
    passed: 'Every item is answered and none is "No" or "Defect".',
    open: 'Items remain unanswered, there are no findings so far.',
    failed: 'At least one item is "No" or "Defect".',
  },
  filters: {
    label: 'Show',
    all: 'All items',
    unanswered: 'Unanswered',
    problems: 'Findings',
    changes: 'Changed',
    any: 'Any',
    anyone: 'Anyone',
    me: 'Me',
    status: {
      released: 'Released',
      unreleased: 'Not released',
    },
    search: 'Search titles',
  },
  views: {
    sortByItems: {
      changedDesc: 'Changed (newest)',
      changedAsc: 'Changed (oldest)',
      createdDesc: 'Created (newest)',
      createdAsc: 'Created (oldest)',
      numberDesc: 'Number (newest first)',
      numberAsc: 'Number (oldest first)',
      titleAsc: 'Title (A → Z)',
      titleDesc: 'Title (Z → A)',
      typeAsc: 'Type (A → Z)',
      verdictAsc: 'Result (A → Z)',
      releasedDesc: 'Released (newest)',
    },
    groupByItems: {
      type: 'Type',
      owner: 'Belongs to',
      verdict: 'Result',
      status: 'Status',
    },
  },
  expandAll: 'Expand all',
  collapseAll: 'Collapse all',
  sectionProgress: '{answered} of {total} answered',
  sectionProblems: 'Findings: {count}',
  remark: 'Remark',
  addRemark: 'Add remark',
  removeRemark: 'Hide remark',
  noMatches: 'No items match the filter.',
  see: 'See {items}',
  itemReference: '{section}, item {item}',
  methodsLabel: 'Verification',
  methodsLegend: 'Verification methods',
  methods: {
    A: 'Visual inspection',
    B: 'Practical test',
    C: 'Measurement',
    D: 'Observation during operation',
    E: 'Review of application-specific schematics and plans',
    F: 'Review of safety-related software',
    G: 'Review of the task-based risk assessment',
    H: 'Review of layout drawings and documents',
    I: 'Review of specifications and information for use',
  },
  references: {
    introduction: 'Introduction',
    table: 'Table {table}',
    article: 'Art. {article}',
    annex: 'Annex {annex}',
    annexPoint: 'Annex {annex} {point}',
    machinery: 'Annex {annex} {point}',
  },
  documents: {
    iso4413: 'ISO 4413:2010',
    iso4414: 'ISO 4414:2010',
    iso12100: 'ISO 12100:2010',
    iso13850: 'ISO 13850:2015',
    iso1219_1: 'ISO 1219-1',
    iso1219_2: 'ISO 1219-2',
    iec81346_2: 'IEC 81346-2',
    iec60204_1: 'IEC 60204-1',
    ped: 'Directive 2014/68/EU',
    spvd: 'Directive 2014/29/EU',
    en14359: 'EN 14359',
    en286_1: 'EN 286-1',
    en856: 'EN 856',
    iso13732_1: 'ISO 13732-1',
    ifaValves: 'IFA test principles for valves',
    iso10218_1: 'ISO 10218-1',
    iso10218_2: 'ISO 10218-2',
    iso13849_1: 'ISO 13849-1',
    iec62061: 'IEC 62061',
    iso13854: 'ISO 13854',
    iso13855: 'ISO 13855',
    iso13857: 'ISO 13857',
    iso14119: 'ISO 14119',
    iso14120: 'ISO 14120',
    iso14122: 'ISO 14122',
    iso11161: 'ISO 11161',
    iec61496_1: 'IEC 61496-1',
    isoTs15066: 'ISO/TS 15066',
  },
  summaryCard: {
    title: 'Result',
    completion: '{percent} % answered',
    open: 'Open',
    problems: 'Findings',
    noProblems: 'No findings so far.',
  },
  hydraulics: {
    parts: {
      documentation: 'Documentation review',
      machine: 'Inspection of the built machine',
      instructions: 'Instructions for use',
    },
    sections: {
      assessment: 'Assessment of the hydraulic equipment',
      circuit: 'Circuit diagrams',
      sizing: 'Dimensioning',
      cleanliness: 'Fluid cleanliness',
      emergencyStop: 'Emergency stop',
      accumulatorDesign: 'Hydraulic accumulators',
      servoValves: 'Controls with servo or proportional valves',
      reservoir: 'Reservoir',
      marking: 'Marking',
      assembly: 'Assembly',
      piping: 'Pipes and hoses',
      bleeding: 'Bleed points and test points',
      maintenance: 'Ease of maintenance',
      electrical: 'Electrical equipment (checked by a qualified electrician)',
      energySupply: 'Energy supply',
      fluctuations: 'Energy fluctuations (pressure and flow)',
      actuators: 'Manual controls',
      indicators: 'Measuring and indicating devices',
      adjustments: 'Adjustment devices on safety-related components',
      cylinders: 'Stroke end stops and piston rod protection',
      temperature: 'Surface temperature and fire risk',
      rescue: 'Freeing trapped persons',
      accumulatorCheck: 'Hydraulic accumulators',
      tests: 'Tests',
      manual: 'Hydraulic part of the instructions',
    },
    items: {
      assessment: {
        documents:
          'Are the following documents available: circuit diagrams, parts lists, data sheets of all components, instructions for use, safety data sheets of the hydraulic fluid and any other documents needed?',
        circuitFunctions: 'Are the hydraulic components suitable for performing the functions of this circuit?',
        typeCStandard: 'Has it been checked whether a type-C standard applies to the machine? Note its title in the remark.',
        typeCRequirements:
          'If a type-C standard applies: are its requirements for the hydraulic equipment that go beyond ISO 4413 taken into account?',
        riskAssessment:
          'Has the risk assessment of the machine to ISO 12100 been evaluated for hazards that lead to safety requirements for the hydraulic equipment, and are these requirements taken into account?',
      },
      circuit: {
        iso1219: 'Are the circuit diagrams drawn to ISO 1219-2?',
        layout: 'Are the lines drawn simply, so that every circuit path can be followed, and with as few crossings as possible?',
        symbols: 'Are graphical symbols to ISO 1219-2 used, and do the reference designations follow IEC 81346-2?',
        restPosition: 'Are the symbols shown unactuated, in the de-energised rest position?',
        assemblies: 'Are assemblies marked off by enclosure lines?',
        crossDesignations:
          'Do the designations of the relevant components match across the hydraulic, electrical and electronic circuit diagrams?',
        portMarking: 'Are all ports identified?',
        sheetTransitions: 'Are line transitions between separate circuit diagram sheets identified?',
        partsList: 'Is a parts list shown on the circuit diagram?',
        supplementary:
          'Is supplementary information available where needed, such as a function diagram, a layout plan or a sequence chart?',
        unexpectedStart:
          'To prevent unexpected start-up, can the system be completely isolated from its energy sources and its stored energy be dissipated?',
        circuitFunction: 'Does the circuit shown in the diagram perform all required functions?',
        isolation:
          'Is complete isolation from the energy source and release of the fluid pressure ensured, by disconnecting the electrical supply (main switch) and by mechanical locking, for example shut-off valves locked in the closed position, with the pressure in the system released?',
        safePositionValves:
          'Are the valves identified that must move to or hold a defined safe position if the control fails? List them in the remark.',
        safePositionMeans: 'Are these valves held in that position by spring offset or by a detent?',
        overpressure:
          'Are all parts of the system protected against excessive pressure, including pressure intensification, for example by pressure relief valves or by pressure control at the pump (the latter only within the limits of ISO 4413, 5.2.2.2)?',
        pressureLoss:
          'If loss of pressure or leakage could cause a hazard: are measures taken against it, for example pilot-operated check valves or mechanical locking?',
        fluctuations:
          'If energy fluctuations (loss of power, critical pressure drop) could cause a hazard: are the permissible limits specified, for example in the circuit diagram and the instructions, and are fluctuations indicated, pressure for example by a gauge or warning light and flow by a flow meter or warning light?',
        switching: 'Is it ensured that switching the energy supply on or off cannot cause a hazard?',
        failureReturn:
          'Is it ensured that failure or return of the energy supply cannot cause a hazard, for example by monitoring the pressure?',
        pressureSurges: 'Is the system designed so that pressure surges and pressure intensification cannot cause a hazard?',
        surgeConfirmation:
          'Is there a confirmation from the manufacturer of the system or machine of the measures chosen against pressure surges and pressure intensification?',
        testPoints: 'Are the required test points shown?',
        bleedPoints: 'Are the required bleed points and drain points shown?',
        sequenceHazard:
          'If the system has sequence controls: is it ensured that a malfunction in a pressure- or time-dependent step sequence cannot cause a hazard?',
        sequencePosition: 'Where such a malfunction could cause a hazard: are position-dependent controls used instead?',
        linkedComponents:
          'If failure of interlinked components, operated automatically or by hand, could cause a hazard: are interlocks or other safety measures provided?',
        interlockInterruption: 'Do the interlocks interrupt all working steps, without the interruption itself causing a hazard?',
        externalForces:
          'Is excessive pressure caused by external forces on the actuators prevented, for example by additional pressure relief valves or mechanical measures?',
        drainBack:
          'Where it would cause a hazard, is fluid prevented from draining away when the system is switched off, for example by back-pressure valves?',
      },
      sizing: {
        designData:
          'Are the design data on which the dimensioning is based documented: maximum operating pressure, pressures in subsystems, pilot pressure, operating temperature range, cleanliness level and hydraulic fluid (standard designation)? Note the values in the remark.',
        componentRatings:
          'Are all parts of the system selected to withstand the expected operating pressures and temperatures and to suit the intended fluid, or is this confirmed by the manufacturer?',
        cylinderSizing:
          'If the system has cylinders: are they adequately sized for pressure, bending and buckling, proven by calculation or data sheet?',
        cylinderFasteners:
          'Are the fastening screws of the cylinders and their mountings (for example foot plates) adequately sized and as far as possible free of shear forces?',
        valveMisassembly:
          'Is incorrect mounting of valves prevented, for example by the hole pattern, a locating pin, or notes in the circuit diagram and the instructions (such as for 2-way cartridge valves)?',
      },
      cleanliness: {
        devices: 'Are devices for keeping the fluid clean provided, for example filters, particle counters or separators?',
        filterTypes:
          'Are the filters of the system identified (air breather, pressure filter, return, suction or off-line filter)? List them in the remark.',
        breatherFineness:
          'Air breather (open systems only): is its filtration at least as fine as the filtration the component manufacturers require on the fluid side?',
        breatherConditions: 'Air breather: does its design suit the ambient and operating conditions?',
        breatherFlow: 'Air breather: is its permissible flow rate higher than the total flow into and out of the reservoir?',
        pressureFilter:
          'Pressure filter: does the filtration meet the requirements of the component manufacturers, is its nominal pressure sufficient, and is it suitable for the flow rate, the fluid and the operating temperature range?',
        pressureFilterIndicator: 'Pressure filter: is a contamination indicator fitted?',
        returnFilter:
          'Return and other filters: does the filtration meet the requirements of the component manufacturers, is the nominal pressure sufficient, and is the filter suitable for the flow rate, the fluid and the operating temperature range?',
        returnFilterIndicator: 'Return and other filters: is a contamination indicator fitted?',
        returnBackPressure:
          'Return filter: if increased back pressure could cause a hazard, are measures taken against it, for example a contamination indicator with bypass, or an electrical indicator with shutdown or bypass?',
      },
      emergencyStop: {
        equipped: 'Is the machine equipped with an emergency stop function?',
        devices:
          'Is the emergency stop initiated by a deliberate manual action on suitable devices, for example emergency stop push-buttons, a pull-cord switch, a foot switch without guard, or the main switch where it is designed for emergency stop use? Note the devices in the remark.',
        effect:
          'Does actuating the emergency stop have the intended effect, for example switching off the pump drive, shutting off the flow to the actuators, unloading or isolating the accumulators, unloaded circulation of the pump flow, holding the clamping pressure, or retracting? Note the effects in the remark.',
        valves:
          'Are the valves in the emergency stop circuit suitable to achieve these effects, for example a 4/3 directional valve with closed centre position to stop a motion, or valves that move to their safe position when de-energised?',
        allModes: 'Is the emergency stop effective in all operating modes, for example automatic, semi-automatic and setting?',
        servoSuitable: 'Can servo or proportional valves in the emergency stop circuit meet these requirements as well?',
        manualValves:
          'If not: can additional, manually operated valves bring the actuators into a defined safe position in an emergency?',
      },
      accumulatorDesign: {
        data: 'If the system has hydraulic accumulators: are their volume V in litres and the product p × V in bar × litres documented? Note the values in the remark.',
        directive:
          'Has it been determined whether the accumulator falls under Directive 2014/68/EU (pressure equipment) or Directive 2014/29/EU (simple pressure vessels)?',
        category:
          'For accumulators under Directive 2014/68/EU: has the conformity assessment category been determined? Note it in the remark.',
        certificates:
          'Are the certificates required for the accumulator available, for example the EU declaration of conformity and the EU-type examination certificate?',
        inspectionBeforeUse:
          'Is there a certificate of the inspection before first use, carried out by an authorised body or a competent person according to national rules?',
        safetyDevices:
          'Are the following safety devices present and shown in the circuit diagram: pressure gauge, safety valve, shut-off valve and pressure release valve?',
        switchedOff:
          'When the system is switched off, is the accumulator either unloaded automatically on the fluid side or reliably isolated on the fluid side?',
        holdPressure: 'Is it specified whether the pressure must be held after the system is switched off?',
        gasRelief: 'Where required, is pressure limitation provided on the gas side?',
      },
      servoValves: {
        controlHazard:
          'If actuators are controlled by servo or proportional valves whose malfunction or faulty control could cause a hazard: are measures provided to keep or regain control over these actuators?',
        unintendedMotion:
          'If the speed of actuators is controlled by servo or proportional valves and unintended motion could cause a hazard: are measures provided to hold the actuators in a safe position or move them into one?',
        mainFilter:
          'Is a full-flow filter fitted in the supply line to every servo or proportional valve whose malfunction through contamination could cause a hazard?',
        filterNoBypass: 'Is this filter without bypass and fitted with a contamination indicator?',
        filterCollapse: 'Is the collapse pressure rating of the filter element above the maximum operating pressure of the system?',
        filterBlocking: 'Is a hazard from a blocked filter prevented by suitable measures, for example a pressure relief valve?',
      },
      reservoir: {
        capacity:
          'Is the reservoir designed to hold all the fluid that can drain into it in normal operation and maintenance, to keep the fluid level at a safe height in all working cycles, and to dissipate enough heat in normal operation where no heat exchanger is fitted?',
        pressurised:
          'For pressurised reservoirs: are the special requirements met, in particular an adequately sized pressure relief valve on the air side?',
        accessories:
          'Is the reservoir fitted with a level indicator marked with the maximum and minimum level, a tightly closing filler cap and an air breather?',
      },
      marking: {
        positionMarks:
          'Are the components marked with their item number or letter code from the circuit diagram, on or next to the component?',
        componentData:
          'Are the functional components permanently and legibly marked with the name and short address of the manufacturer or supplier, the product identification and the rated pressure (at least the maximum operating pressure of the system), with symbols to ISO 1219-1 and all ports correctly identified?',
        stackOrder: 'For vertical valve stacks: is the order of the elements marked next to the stack, but not on the stack elements?',
        accumulatorData:
          'Are accumulators additionally marked with the date of manufacture (month and year), gas type and precharge pressure, serial number, maximum allowable pressure, volume in litres, allowable temperature range and, where applicable, the CE marking?',
        valveOperators: 'For non-electrical valve operators: do the markings of the operator and its functions match the circuit diagram?',
        testDrainPoints: 'Are the test and drain points marked as in the circuit diagram and easily accessible?',
        accumulatorWarning:
          'Does a system with accumulators carry a clearly visible warning sign reading: "Caution, system contains accumulators. Depressurise the system before starting maintenance work."?',
        accumulatorMaintenanceNote:
          'For accumulators whose fluid side stays pressurised when the system is switched off: is a note on safe maintenance placed clearly visibly on or near the accumulator?',
        interchangeableLines: 'Are line ends that could be interchanged marked as in the circuit diagram?',
      },
      assembly: {
        conformsToDiagram: 'Is the hydraulic system built as shown in the circuit diagram?',
        mountingPosition: 'Does the mounting position of the components match the specifications of their manufacturers?',
        cylinderFasteners:
          'Are all fastening screws of the cylinders and their mountings (for example foot plates) adequately sized and free of shear forces?',
        fastenersSecured: 'Are they fastened so that they resist loosening from shock and vibration?',
        mechanicalValves: 'Are mechanically operated valves mounted so that their operating device, for example a cam, cannot damage them?',
        intensification: 'Are measures against unintended pressure intensification present and effective?',
        returnPressure:
          'Are hazards from increased return-line pressure and from the sealing function of quick-release couplings prevented?',
      },
      piping: {
        pipeSupport:
          'Are pipes adequately supported, with clamps at both ends and at points along their whole length, and are the recommended distances between supports, bends and fittings kept?',
        supportDamage: 'Are the supports designed so that they do not damage the pipes? Welding pipes to supports is not permitted.',
        componentsOnPipes:
          'If pipes are used to support components: is it ensured that the mass of the components cannot cause shocks or vibration that overload the pipes?',
        notAStep: 'Are pipes and hoses routed so that they cannot be used as a step or ladder?',
        wrongConnection:
          'Are pipes and hoses, including their connections, arranged or designed so that a wrong connection that causes a hazard cannot be made, for example by different threads or the shape of the line?',
        wrongConnectionMarking: 'If not: are they clearly and permanently marked as in the circuit diagram?',
        protectedRouting:
          'Are pipes and hoses arranged so that they are protected against all foreseeable damage and do not hinder access for adjusting, repairing and replacing components or for operating the system?',
        hoseAssemblyMarking:
          'Are hose assemblies marked, for example on the ferrule, with the name or mark of the manufacturer, the maximum allowable working pressure in bar (for example PN 350) and the year and month of assembly?',
        hoseMarking:
          'Is the hose marked with the name or mark of its manufacturer, the standard and type (for example EN 856 4SP), the nominal size and the quarter and year of manufacture?',
        notReused:
          'As far as can be seen, are the hose assemblies made from hoses that were not previously part of another hose assembly?',
        serviceLife: 'Have the hose assemblies and hoses not exceeded the storage and service life recommended by their manufacturer?',
        hoseInstallation:
          'Are the hose assemblies installed so that they have the length needed to avoid damaging stress such as kinking or tension in operation, the minimum bend radius is kept, twisting during installation and operation is kept to a minimum, there are no chafing points, the markings stay readable (not painted over) and any coating is compatible with the hose material (confirmed by the manufacturer)?',
        whipProtection:
          'Where failure of a hose assembly (pulling out, bursting) would cause a hazard such as whipping or fluid ejection, for example at operator stations or walkways: are suitable protective measures in place, such as fastening, restraints or shielding?',
        quickCouplings: 'Where quick-release couplings are used: do the outlet and inlet ports seal automatically when uncoupled?',
      },
      bleeding: {
        bleedPoints: 'Where bleeding is required: are bleed points present?',
        bleedMarked: 'Are they clearly and unmistakably marked?',
        bleedAccess: 'Do they work automatically, or are they easily and safely accessible?',
        bleedSafe: 'Can the trapped air escape without endangering persons?',
        singleActing:
          'If single-acting cylinders are present: are their air vent ports designed or arranged so that the trapped air escapes without endangering persons?',
        testPoints: 'Are the required test points present?',
        testPointsAccess: 'Are they easily accessible?',
        testPointsMarked: 'Are they clearly and unmistakably marked?',
      },
      maintenance: {
        access:
          'Are the components arranged so that they are easily and safely accessible for maintenance, including easy and safe draining and filling of the reservoir?',
        removal:
          'Are measures taken, or the components arranged and connected, so that removing them from the system keeps fluid loss to a minimum, does not require draining the reservoir and does not require unnecessary removal of adjacent components?',
      },
      electrical: {
        solenoidVoltage: 'Are the solenoids of the hydraulic valves designed for reliable operation within the tolerance of the rated voltage?',
        solenoidProtection: 'Do the solenoids have the degree of protection (IP code) needed against ingress of liquids and dust?',
        terminalBoxes:
          'Do the terminal boxes have a suitable degree of protection, captive fasteners for the cover and cable entries with strain relief?',
        coversSecured:
          'Are the covers of terminal strips and terminal boxes on electrically operated valves secured against loss, for example by a chain?',
      },
      energySupply: {
        switching: 'Does switching the energy supply on or off, or its return, cause no hazard?',
      },
      fluctuations: {
        indicators: 'Are the indicators and warning devices needed for energy fluctuations present and suitable?',
      },
      actuators: {
        design:
          'Are the manual controls clearly visible, clearly and permanently marked, consistent in their movement with the effect they control, designed or guarded against unintended operation, and ergonomically designed and arranged?',
        multiFunction: 'Where one control has several different effects: is the effect selected clearly indicated?',
      },
      indicators: {
        visible: 'Where measuring devices are fitted: are their displays clearly visible and accessible?',
        gauges:
          'For pressure gauges, additionally: is the range sufficient, are limit values marked, is damping fitted where needed, is the display easy to read, and are the setting devices of gauges with contacts adequately secured where they are safety-related?',
      },
      adjustments: {
        tamperProof:
          'Are adjustment devices on safety-related components designed or protected so that they cannot be changed without deliberate action, for example adjustment only with a tool, sealing, or fixed limits of the adjustment range?',
      },
      cylinders: {
        endStops:
          'Where stroke end stops are required: are they present, correctly positioned and adequately sized, verified by a test on the prototype, for example by running into them at maximum speed?',
        rodProtection: 'Where foreseeable damage such as nicks, scratches or corrosion makes it necessary: is the piston rod protected?',
      },
      temperature: {
        hotSurfaces:
          'Where hot surfaces occur in working and traffic areas during operation: are they guarded? Limit temperatures are given in ISO 13732-1.',
        hoseFire: 'Are hose assemblies fastened or shielded so that there is no fire risk, for example near hot surfaces?',
      },
      rescue: {
        rescuePossible:
          'If the risk assessment shows residual risks that may require freeing trapped persons: can persons be freed, for example by operating valves or controls, depressurising the system or removing components?',
        rescueNotes:
          'Where needed, are instructions for freeing persons provided, for example signs on valves, on other controls or on the machine?',
      },
      accumulatorCheck: {
        shutdown:
          'When the system is switched off, is the accumulator automatically depressurised, or isolated by a lockable main control device?',
        manualRelease: 'Is a manual pressure release device present?',
        warningSign: 'Is a warning sign present reading: "Caution, accumulator. Depressurise before repair or dismantling."?',
        remoteLines: 'Do lines that are connected directly to the accumulator but are not close to it carry a warning sign?',
        gasNote: 'Are the gas precharge pressure and the gas type (for example nitrogen) indicated on the accumulator?',
        noModifications: 'Is the accumulator free of visible inadmissible modifications such as machining or welding?',
      },
      tests: {
        functions: 'Are all functions of the system performed as intended?',
        safetyDevices: 'Do all safety devices work as intended?',
        emergencyStop: 'Does the emergency stop act as specified?',
        noNewHazards: 'Does actuating the emergency stop create no additional hazards, also in linked installations?',
        restart: 'After the emergency stop is released, does the system need a new start command?',
        pressureTest: 'Does a pressure test at maximum operating pressure pass without faults such as leakage?',
        speedLimits: 'Are the specified speed limits of cylinders and motors not exceeded?',
        noBending: 'During the function test, do piston rods and cylinders show no bending or twisting (visual check only)?',
      },
      manual: {
        contents:
          'Do the instructions contain the intended use, reasonably foreseeable misuse, a description of the hydraulic equipment, the operating pressure limits, the operating temperature limits of fluid and components, the ambient temperature range and other environmental influences such as fire and explosion risks, the hydraulic circuit diagram, the hydraulic parts list and, where needed, the function diagram?',
        transport:
          'Is there information on safe transport: explanations for transport, weight, transport locking and packaging, drawings showing the lifting points, closing of port openings, protection of external threads, special precautions such as retracting piston rods, and marking of the pipes and connections that must be separated for transport?',
        commissioning:
          'Is there information on commissioning and operation: space required including safety distances, permissible ambient conditions such as humidity, temperature and vibration, installation instructions, fastening for safe operation, hazard warnings such as special safety devices, and connections to the energy supply?',
        fluid: 'Do the instructions state the type and grade of the hydraulic fluid?',
        safetyDataSheet:
          'Do they point out that the safety data sheet of the fluid must be observed in the operating instructions, for example on physical and safety-related protective measures, storage and handling, measures in accidents and fires, toxicology and ecology?',
        disposal: 'Do they contain information on disposal of the fluid?',
        maintenance:
          'Is there information on maintenance and inspection: requirements for personnel, personal protective equipment needed, residual pressures when the system is switched off, fault finding and rectification, draining of reservoir and system, maintenance intervals, safety measures, depressurisation (for example of accumulators), adjustment procedures, recommissioning (for example bleeding and adjusting) and refitting of guards?',
        hoseData: 'Is hose assembly data included, for example storage and service life?',
        periodicInspections: 'Are periodic inspections specified, for example of accumulators and hose assemblies?',
        emergencies:
          'Is there information on emergencies: actuating the emergency stop, retracting, measures on energy failure, freeing trapped persons, suitable fire-fighting equipment and first aid, for example for poisoning, suffocation and burns?',
      },
    },
    hints: {
      circuit: {
        unexpectedStart:
          'Systems with an integrated pressure source allow other measures, such as disconnecting the electrical supply. Where pressure must be held after isolation, for example in a circuit with an accumulator, other measures are possible as well.',
        pressureSurges:
          'For example by suitable piping, pressure relief valves, additional damping such as an accumulator, and suitable components: directional valves with a suitable spool design, cylinders with end-position cushioning, continuous valves with suitable control characteristics.',
        testPoints:
          'Test points can be needed where settings or checks are made (for example on working and pilot lines to set pressure relief valves, or to check pilot-operated check valves), where changes in temperature, pressure or flow could cause hazards (for example in tank or leakage lines and at heat exchangers), and for maintenance.',
      },
      sizing: {
        componentRatings:
          'This applies to pumps and motors, cylinders, valves, devices for fluid cleanliness, pipes, fittings and manifold passages, hose assemblies (standardised, for example to EN 853, EN 854, EN 856, EN 857 or ISO 18752), reservoirs, accumulators and heat exchangers.',
      },
      emergencyStop: {
        devices:
          'Protective devices such as light curtains, laser scanners or radar sensors trigger a protective stop, not an emergency stop. An emergency stop is always initiated by a deliberate manual action (ISO 13850).',
      },
      servoValves: {
        controlHazard:
          'For example safe electrical isolation of the control power to the valve solenoids, combined with valves that are suitable by design (ports to be closed in the rest position have sufficient positive overlap, and the rest position is reached by spring force when the control power is removed), or with additional conventional valves where the servo or proportional valves are not suitable by design.',
        unintendedMotion: 'The measures can be the same as those for keeping or regaining control.',
      },
      piping: {
        quickCouplings: 'Sealing the outlet port must not defeat a safety function, for example of a spring-applied brake.',
      },
    },
  },
  pneumatics: {
    parts: {
      documentation: 'Documentation review',
      machine: 'Inspection of the built machine',
      instructions: 'Instructions for use',
    },
    sections: {
      assessment: 'Assessment of the pneumatic equipment',
      circuit: 'Circuit diagrams',
      sizing: 'Dimensioning',
      airTreatment: 'Compressed air treatment',
      emergencyStop: 'Emergency stop',
      vesselDesign: 'Pressure vessels',
      servoValves: 'Controls with servo or proportional valves',
      marking: 'Marking',
      assembly: 'Assembly',
      piping: 'Pipes and hoses',
      exhaust: 'Exhaust air and test points',
      maintenance: 'Ease of maintenance',
      electrical: 'Electrical equipment',
      energySupply: 'Energy supply and fluctuations',
      actuators: 'Manual controls',
      indicators: 'Measuring and indicating devices',
      adjustments: 'Adjustment devices on safety-related components',
      cylinders: 'Stroke end stops and piston rod protection',
      fire: 'Fire risk',
      rescue: 'Freeing trapped persons',
      vesselCheck: 'Pressure vessels',
      tests: 'Tests',
      manual: 'Pneumatic part of the instructions',
    },
    items: {
      assessment: {
        documents:
          'Are the following documents available: circuit diagrams, parts lists, data sheets of all components, instructions for use and any other documents needed?',
        circuitFunctions: 'Are the pneumatic components suitable for performing the functions of this circuit?',
        typeCStandard: 'Has it been checked whether a type-C standard applies to the machine? Note its title in the remark.',
        typeCRequirements:
          'If a type-C standard applies: are its requirements for the pneumatic equipment that go beyond ISO 4414 taken into account?',
        riskAssessment:
          'Has the risk assessment of the machine to ISO 12100 been evaluated for hazards that lead to safety requirements for the pneumatic equipment, and are these requirements taken into account?',
      },
      circuit: {
        iso1219: 'Are the circuit diagrams drawn to ISO 1219-2?',
        layout: 'Are the lines drawn simply, so that every circuit path can be followed, and with as few crossings as possible?',
        symbols: 'Are graphical symbols to ISO 1219-2 used, and do the reference designations follow IEC 81346-2?',
        restPosition: 'Are the symbols shown unactuated, in the de-energised rest position?',
        lineColours: 'Are the lines shown in the colours of the actual tubing?',
        assemblies: 'Are assemblies marked off by enclosure lines?',
        crossDesignations:
          'Do the designations of the relevant components match across the pneumatic, electrical and electronic circuit diagrams?',
        portMarking: 'Are all ports identified?',
        sheetTransitions: 'Are line transitions between separate circuit diagram sheets identified?',
        partsList: 'Is a parts list shown on the circuit diagram?',
        supplementary:
          'Is supplementary information available where needed, such as a function diagram, a layout plan or a sequence chart?',
        unexpectedStart:
          'To prevent unexpected start-up, can the system be completely isolated from its energy sources and its stored energy be dissipated?',
        safePositionValves:
          'Are the valves identified that must move to or hold a defined safe position if the control fails or a protective device is actuated? List them in the remark.',
        safePositionMeans:
          'Do these valves move to their safe position when de-energised, and are they held there by spring offset or a physically similar principle?',
        manualOverride:
          'Where electrically operated valves must also be operable by hand for safety reasons: do they have a manual override that cannot be operated unintentionally and does not latch?',
        overpressure: 'Are all parts of the system protected against excessive pressure, for example by pressure regulating valves?',
        pressureLoss: 'Is it ensured that loss of pressure or leakage cannot cause a hazard?',
        switching: 'Is it ensured that switching the energy supply on or off cannot cause a hazard?',
        failureReturn: 'Is it ensured that failure or return of the energy supply cannot cause a hazard?',
        fluctuations:
          'If energy fluctuations could cause a hazard: are the permissible limits specified, are fluctuations detected and indicated, and are suitable measures taken?',
        smoothMotion: 'Where smooth acceleration or deceleration of movements is needed: is it provided?',
        pressureSurges: 'Is the system designed so that pressure surges and pressure intensification cannot cause a hazard?',
        testPoints: 'Are test points provided where they are needed?',
        sequence: 'Is it ensured that malfunctions in the step sequence cannot cause a hazard?',
        externalForces: 'Is excessive pressure caused by external forces on the pneumatic system prevented?',
      },
      sizing: {
        designData:
          'Are the design data on which the dimensioning is based documented: maximum operating pressure, pressures in subsystems, pilot pressure, control voltage and operating temperature range? Note the values in the remark.',
        componentRatings: 'Are all parts of the system selected to withstand the expected pressures, temperatures and other loads?',
        cylinderSizing: 'Are the cylinders adequately sized for pressure, bending and buckling, proven by calculation or data sheet?',
        cylinderFasteners:
          'Are the fastening screws of the cylinders and their mountings adequately sized and as far as possible free of shear forces?',
        valveMisassembly: 'Is incorrect mounting of valves prevented?',
      },
      airTreatment: {
        contaminants:
          'Are measures taken to keep harmful solid, liquid and gaseous substances out of the compressed air, for example filters, separators, dryers or lubricators?',
        filtration:
          'Is the filtration grade sufficient for the components and for the ambient conditions at the intended place of installation?',
        filterDegradation: 'Is it ruled out that deteriorating filter performance leads to a hazardous situation?',
      },
      emergencyStop: {
        equipped: 'Is the machine equipped with an emergency stop function?',
        devices:
          'Is the emergency stop initiated by a deliberate manual action on suitable devices, for example emergency stop push-buttons, a pull-cord switch, or the main switch where it is designed for emergency stop use? Note the devices in the remark.',
        effect:
          'Does actuating the emergency stop have the intended effect, for example switching off the central main valve, shutting off the flow to the actuators, venting or isolating the pressure vessels, holding pressure in subsystems (clamping pressure, holding loads up), or retracting? Note the effects in the remark.',
        valves:
          'Are the valves in the emergency stop circuit suitable to achieve these effects, for example a 5/3 directional valve with closed centre position to stop a motion, or valves that move to their safe position when de-energised?',
        allModes: 'Is the emergency stop effective in all operating modes, for example automatic, semi-automatic and setting?',
        servoSuitable: 'Can servo or proportional valves in the emergency stop circuit meet these requirements as well?',
        additionalValves: 'If not: can additional valves bring the actuators into a defined safe position in an emergency?',
      },
      vesselDesign: {
        data: 'If the system has pressure vessels (air receivers): are their volume V in litres and the product p × V in bar × litres documented? Note the values in the remark.',
        directive:
          'Has it been determined whether the pressure vessel falls under Directive 2014/68/EU (pressure equipment) or Directive 2014/29/EU (simple pressure vessels)?',
        category:
          'For pressure vessels under Directive 2014/68/EU: has the conformity assessment category been determined? Note it in the remark.',
        certificates:
          'Are the certificates required for the pressure vessel available, for example the EU declaration of conformity and the EU-type examination certificate?',
        inspectionBeforeUse:
          'Is there a certificate of the inspection before first use, carried out by an authorised body or a competent person according to national rules?',
        safetyDevices:
          'Are the following safety devices present and shown in the circuit diagram: pressure gauge, safety valve, shut-off valve and pressure release valve?',
        switchedOff:
          'When the system is switched off, is the pressure vessel either vented automatically on the air side or reliably isolated on the air side?',
        holdPressure: 'Is it specified whether the pressure must be held after the system is switched off?',
      },
      servoValves: {
        controlHazard:
          'If actuators are controlled by servo or proportional valves whose malfunction or faulty control could cause a hazard: are measures provided to keep or regain control over these actuators?',
        unintendedMotion:
          'If the speed of actuators is controlled by servo or proportional valves and unintended motion could cause a hazard: are measures provided to hold the actuators in a safe position or move them into one?',
        filtration:
          'Is filtration as specified by the manufacturer ensured in the supply line to every servo or proportional valve whose malfunction through contamination could cause a hazard?',
      },
      marking: {
        positionMarks:
          'Are the components marked with their item number or letter code from the circuit diagram, on or next to the component?',
        componentData:
          'Are the functional components permanently and legibly marked with the name of the manufacturer or supplier, the product identification and the rated pressure, with symbols to ISO 1219-1?',
        stackOrder: 'For vertical valve stacks: is the order of the elements marked next to the stack, but not on the stack elements?',
        vesselMarking:
          'Are simple pressure vessels to EN 286-1 (below 30 bar and 10 000 bar × litres, cylindrical, series production) marked with the date of manufacture, the CE marking, the serial or batch number, the maximum allowable pressure, the volume in litres and the allowable temperature range?',
        valveOperators: 'For non-electrical valve operators: do the markings of the operator and its functions match the circuit diagram?',
        testDrainPoints: 'Are the test and drain points marked as in the circuit diagram and easily accessible?',
        vesselWarning:
          'Does a system with pressure vessels carry a clearly visible warning sign reading: "Caution, system contains pressure vessels. Depressurise the system before starting maintenance work."?',
        vesselMaintenanceNote:
          'If a pressure vessel stays pressurised after the system is switched off: are notes on safe maintenance placed clearly visibly?',
        interchangeableLines: 'Are line ends that could be interchanged marked as in the circuit diagram?',
      },
      assembly: {
        conformsToDiagram: 'Is the pneumatic system built as shown in the circuit diagram?',
        mountingPosition: 'Does the mounting position of the components match the specifications of their manufacturers?',
        cylinderFasteners:
          'Are all fastening screws of the cylinders and their mountings adequately sized and free of shear forces?',
        fastenersSecured: 'Are they fastened so that they resist loosening from shock and vibration?',
        mechanicalValves: 'Are mechanically operated valves mounted so that cams or trip dogs cannot damage them?',
        intensification: 'Are measures against unintended pressure intensification present and effective?',
        backPressure:
          'Are hazards from back pressure in valve manifolds, in shared exhaust lines or from silencers in exhaust ports prevented?',
        bowlGuards:
          'Do non-metallic bowls of filters, separators, pressure regulators and lubricators larger than 1 bar × litre have a bowl guard?',
      },
      piping: {
        pipeSupport: 'Are pipes adequately supported, with clamps at both ends and at points along their whole length?',
        supportDamage: 'Are the supports designed so that they do not damage the pipes? Welding pipes to supports is not permitted.',
        componentsOnPipes:
          'If pipes are used to support components: is it ensured that the mass of the components cannot cause shocks or vibration that overload the pipes?',
        notAStep: 'Are pipes and hoses routed so that they cannot be used as a step, ladder or climbing aid?',
        wrongConnection:
          'Are pipes and hoses, including their connections, arranged or designed so that a wrong connection that causes a hazard cannot be made, for example by different threads or the shape of the line?',
        wrongConnectionMarking: 'If not: are they clearly and permanently marked as in the circuit diagram?',
        protectedRouting:
          'Are pipes and hoses arranged so that they are protected against all foreseeable damage and do not hinder access for adjusting, repairing and replacing components or for operating the system?',
        hoseMarking:
          'Is the following shown permanently and legibly on the hose: name and address of the manufacturer, date of manufacture, rated pressure and, optionally, the nominal inside diameter?',
        tubeMarking:
          'Is the following shown permanently and legibly on plastic tubing: name or mark of the manufacturer, date of manufacture and, optionally, the nominal inside diameter?',
        notReused: 'Are the hose assemblies made from hoses that were not used before?',
        serviceLife: 'Have the hose assemblies not exceeded the storage and service life recommended by their manufacturer?',
        hoseInstallation:
          'Are the hose assemblies installed so that they have the length needed to avoid damaging stress such as kinking or tension in operation without being unnecessarily long, the minimum bend radius is kept, twisting during installation and operation is kept to a minimum, there are no chafing points, the markings stay readable and any coating is compatible with the hose material?',
        whipProtection:
          'Where failure of a hose assembly (pulling out, bursting) would cause a hazard such as whipping or escaping compressed air, for example at operator stations or travel paths: are suitable protective measures in place, such as fastening, restraints or shielding?',
        quickCouplings:
          'Where quick-release couplings are used: do the outlet and inlet ports seal automatically when uncoupled, is it impossible for a coupling part to be ejected or for compressed air to escape, and is pressure relief provided?',
      },
      exhaust: {
        exhaustAir:
          'Is the system built so that air exhausted in normal operation causes no hazard, for example through low outflow velocity, the position and direction of the outlets, and the arrangement of filters, filter silencers and shields?',
        singleActing:
          'If single-acting cylinders are present: are their air vent ports designed and arranged so that the trapped air is expelled without endangering persons?',
        testPoints: 'Are the required test points present, easily accessible, and clearly and unmistakably marked?',
      },
      maintenance: {
        access: 'Are the components arranged so that they are easily and safely accessible for maintenance?',
        residualPressure:
          'If components remain pressurised after the energy supply is disconnected: can the pressure be released without hazard, are measures that are needed, such as supports, provided, and is this pointed out?',
        removal:
          'Are measures taken, or the components arranged and connected, so that removing them from the system does not require unnecessary removal of adjacent components?',
      },
      electrical: {
        solenoidVoltage: 'Are the solenoids of the pneumatic valves designed for reliable operation at the minimum and maximum voltage?',
        solenoidProtection: 'Do the solenoids have the degree of protection (IP code) needed against ingress of liquids and dust?',
        terminalBoxes:
          'Do the terminal boxes have a suitable degree of protection, captive fasteners for the cover and cable entries with strain relief?',
        coversSecured: 'Are the covers of terminal strips and terminal boxes on electrically operated valves secured against loss?',
      },
      energySupply: {
        switching: 'Does switching the energy supply on or off, or its return, cause no hazard?',
        indicators: 'Are the indicators and warning devices needed for energy fluctuations present?',
      },
      actuators: {
        design:
          'Are the manual controls clearly visible and arranged outside the danger zone, clearly and permanently marked, consistent in their movement with the effect they control, designed or guarded against unintended operation, and ergonomically designed and arranged?',
        multiFunction: 'Where one control has several effects: is the effect selected clearly indicated?',
        manualOverride:
          'Do the relevant electrically operated valves have manual overrides that achieve the required function, cannot be operated unintentionally and do not latch?',
      },
      indicators: {
        visible:
          'Where measuring devices are fitted: are their displays clearly visible and easily accessible, clearly assigned to their measuring points, and do they work?',
        gauges:
          'For pressure gauges, additionally and where appropriate: is the range sufficient, are limit values marked, is damping fitted where needed, is the display easy to read, and are the setting devices of gauges with contacts adequately secured?',
      },
      adjustments: {
        tamperProof:
          'Are adjustment devices on safety-related components (for example pressure and flow control valves, pressure switches, end-position cushioning) designed so that they cannot be changed without deliberate action, for example adjustment only with a tool, sealing, or fixed limits of the adjustment range?',
      },
      cylinders: {
        endStops:
          'Where stroke end stops are required: are they present, correctly positioned, adequately sized and secured against adjustment?',
        rodProtection: 'Where foreseeable damage such as nicks, scratches or corrosion makes it necessary: is the piston rod protected?',
      },
      fire: {
        hoseFire:
          'Are hoses and flexible tubing fastened or shielded so that there is no fire risk from external influences, for example near hot surfaces?',
        lubricatedExhaust: 'If flammable lubricant is added to the compressed air: is no exhaust port directed at hot surfaces?',
      },
      rescue: {
        rescuePossible:
          'If the risk assessment shows residual risks that may require freeing trapped persons: can persons be freed, for example by operating valves or controls, depressurising the system or removing components?',
        rescueNotes:
          'Where needed, are instructions for freeing persons provided, for example signs on valves, on other controls or on the machine?',
      },
      vesselCheck: {
        shutdown:
          'When the system is switched off, is the pressure vessel automatically depressurised, for example by a spring-return 2/2 directional valve, or isolated by a lockable main control device?',
        warningSign:
          'If it is isolated: is a warning sign present reading: "Caution, pressure vessel. Depressurise before repair or dismantling."?',
        remoteLines: 'Do lines that are connected to the pressure vessel but are not close to it carry a warning sign?',
        noModifications: 'Is the pressure vessel free of visible inadmissible modifications such as machining or welding?',
      },
      tests: {
        functions: 'Are all intended functions performed?',
        safetyDevices: 'Do all safety devices work as intended?',
        emergencyStop: 'Does the emergency stop act as specified?',
        noNewHazards: 'Does actuating the emergency stop create no additional hazards, also in linked installations?',
        restart: 'After the emergency stop is released, does the system need a new start command?',
        pressureTest: 'Does a pressure test at maximum operating pressure pass without faults such as leakage?',
        speedLimits: 'Are the specified speed limits of cylinders and motors not exceeded?',
        noBending: 'During the function test, do piston rods and cylinders show no bending or twisting (visual check only)?',
      },
      manual: {
        contents:
          'Do the instructions contain the intended use, reasonably foreseeable misuse, a description of the pneumatic equipment, the operating pressure limits, the operating temperature limits, the ambient temperature range and other environmental influences, the pneumatic circuit diagram, the pneumatic parts list and, where needed, the function diagram?',
        transport:
          'Is there information on safe transport: explanations for transport, weight, transport locking, drawings showing the lifting points, closing of outlet openings, protection of external threads, special precautions such as retracting piston rods and securing cylinders, and marking of the pipes and connections that must be separated for transport?',
        commissioning:
          'Is there information on commissioning and operation: space required including safety distances and clearance for maintenance, permissible ambient conditions, installation instructions, fastening for safe operation, hazard warnings, and the connection data of the energy supply?',
        lubricants: 'Do the instructions state any lubricant needed in the compressed air?',
        safetyDataSheet:
          'If a lubricant is needed: is its safety data sheet available, and do the instructions point out that it must be observed?',
        maintenance:
          'Is there information on maintenance and inspection: requirements for personnel, personal protective equipment needed, residual pressures when the system is switched off, fault finding and rectification, draining of vessels and system, maintenance intervals, safety measures, depressurisation, adjustment procedures, recommissioning (for example bleeding and adjusting), refitting of guards, hose data such as service life, and periodic inspections, for example of pressure vessels, hose assemblies, cylinders and air service units?',
        emergencies:
          'Is there information on emergencies: actuating the emergency stop, retracting, measures on energy failure, freeing trapped persons, suitable fire-fighting equipment and first aid?',
      },
    },
    hints: {
      circuit: {
        unexpectedStart:
          'Systems with an integrated pressure source allow other measures, such as disconnecting the electrical supply. Where pressure must be held after isolation, for example in a pressure vessel, other measures are possible as well.',
      },
      sizing: {
        componentRatings:
          'This applies among others to air motors, cylinders, valves, air treatment devices, the compressed air itself, pipes, fittings and manifold passages, and pressure vessels.',
      },
      emergencyStop: {
        devices:
          'Protective devices such as light curtains, laser scanners or radar sensors trigger a protective stop, not an emergency stop. An emergency stop is always initiated by a deliberate manual action (ISO 13850).',
      },
      servoValves: {
        controlHazard: 'For example safe electrical isolation of the control power to the valve solenoids.',
        unintendedMotion: 'The measures can be the same as those for keeping or regaining control.',
      },
    },
  },
  robotics: {
    parts: {
      controlPerformance: 'Performance of the safety-related control system',
      design: 'Design and installation',
      motionLimits: 'Limiting robot motion',
      layout: 'Layout',
      modes: 'Operating modes of the robot system',
      pendants: 'Pendants',
      maintenance: 'Maintenance and repair',
      ims: 'Interface to an integrated manufacturing system (IMS)',
      safeguarding: 'Safeguarding',
      collaborative: 'Collaborative operation',
      commissioning: 'Commissioning',
    },
    sections: {
      performanceInfo: 'Performance information',
      performanceLevel: 'Required performance',
      riskBasedPerformance: 'Performance from the risk assessment',
      designConditions: 'Design conditions',
      autoModeSelection: 'Selecting automatic mode',
      controls: 'Actuating controls',
      power: 'Power supply and enclosures',
      bonding: 'Protective bonding',
      isolation: 'Isolation of hazardous energy',
      storedEnergy: 'Release of stored energy',
      stopFunctions: 'Protective stop and emergency stop',
      emergencyStop: 'Emergency stop devices',
      emergencyRecovery: 'Moving the robot in an emergency',
      warnings: 'Warning signs',
      lighting: 'Lighting',
      applicationHazards: 'Hazards of the application',
      enablingDevices: 'Additional enabling devices',
      spaces: 'Safeguarded and restricted space',
      limitingDevices: 'Robot limiting devices',
      dynamicLimiting: 'Dynamic limiting devices',
      perimeter: 'Perimeter safeguarding',
      workingSpace: 'Clearances and access',
      materialHandling: 'Feeding and removing material',
      processObservation: 'Process observation',
      multiRobot: 'Multi-robot cells',
      modeSelection: 'Selecting the operating mode',
      automaticMode: 'Automatic mode',
      automaticSelection: 'Selecting automatic mode',
      automaticStart: 'Starting automatic operation',
      startRestart: 'Start and restart',
      localControl: 'Local control during manual intervention',
      reducedSpeed: 'Manual reduced speed',
      highSpeed: 'Manual high speed',
      remoteControl: 'Remote control',
      pendantGeneral: 'Pendants in general',
      cableless: 'Cableless or detachable pendants',
      multiRobotPendant: 'Pendants for several robots',
      procedures: 'Inspection and maintenance procedures',
      safeAccess: 'Safe access for maintenance',
      guardDesign: 'Guards for maintenance',
      imsHazards: 'Hazards from other equipment',
      imsEmergencyStop: 'Emergency stop in the IMS',
      imsLocalControl: 'Local control in the IMS',
      imsEnabling: 'Enabling devices in the IMS',
      imsModes: 'Mode selection in the IMS',
      imsManual: 'Manual intervention in the IMS',
      safeguardsGeneral: 'Guards and protective devices',
      safeguardSelection: 'Selecting safeguards',
      safeguardInstallation: 'Installing safeguards',
      fixedMovableGuards: 'Fixed and movable guards',
      presenceStart: 'Presence sensing preventing a start',
      presenceClearance: 'Presence sensing for clearances',
      guards: 'Guards',
      guardDimensions: 'Guard dimensions',
      interlockedGuards: 'Interlocking movable guards',
      guardLocking: 'Guard locking',
      entrapment: 'Protection against being trapped',
      sensitiveEquipment: 'Sensitive protective equipment',
      sensitiveStop: 'Sensitive protective equipment for a protective stop',
      presenceSensing: 'Presence-sensing equipment preventing a start',
      manualStations: 'Manual load and unload stations',
      movingStations: 'Moving stations',
      sharedWorkspace: 'Shared workspace at stations',
      openings: 'Openings for material',
      adjacentCells: 'Adjacent cells',
      endEffectors: 'End-effectors and tool changers',
      muting: 'Muting',
      suspension: 'Suspending safeguards',
      collaborativeInfo: 'Information for collaborative operation',
      collaborativeRisk: 'Risk assessment and protective devices',
      collaborativeWorkspace: 'Collaborative workspace',
      collaborativeTransition: 'Changing between autonomous and collaborative operation',
      collaborativeFeatures: 'Safety features',
      monitoredStop: 'Safety-rated monitored stop',
      handGuiding: 'Hand guiding',
      speedSeparation: 'Speed and separation monitoring',
      powerForce: 'Power and force limiting',
      commissioningConcept: 'Commissioning concept',
      interimSafeguarding: 'Interim safeguarding',
      startUp: 'Initial start-up',
    },
    items: {
      performanceInfo: {
        stated:
          'Does the information for use state the performance of the safety-related control system, and the data and criteria used to determine it?',
      },
      performanceLevel: {
        plCategory3: 'Does the safety-related control system achieve PL d with a category 3 structure?',
        sil2: 'Where it is assessed to IEC 62061 instead: does it achieve SIL 2 with a hardware fault tolerance of 1 and a proof test interval of not less than 20 years?',
      },
      riskBasedPerformance: {
        fromRiskAssessment: 'Are the results of the risk assessment used to determine the required performance?',
      },
      designConditions: {
        conditions: 'Is the system designed and are its components selected on the basis of the intended conditions of use?',
      },
      autoModeSelection: {
        outside: 'Is automatic mode selected from outside the safeguarded space?',
      },
      controls: {
        iec60204: 'Do the actuating controls meet IEC 60204-1?',
        noRemoteHazard:
          'Is it ensured that the robot system does not respond to external remote commands or conditions that could cause a hazardous situation?',
      },
      power: {
        sources: 'Do all energy sources meet the requirements of the manufacturer?',
        enclosureDoors:
          'Are the doors of electrical enclosures mounted so that they can be opened fully and escape routes always remain reachable?',
      },
      bonding: {
        iec60204: 'Does the protective bonding meet IEC 60204-1?',
      },
      isolation: {
        provided: 'Are means provided to isolate hazardous energy?',
        marked: 'Are these means clearly marked?',
      },
      storedEnergy: {
        provided: 'Are means provided for the controlled release of hazardous stored energy?',
        marked: 'Are these means clearly marked?',
      },
      stopFunctions: {
        protectiveStop: 'Does the robot system have a protective stop function?',
        emergencyStop: 'Does the robot system have an independent emergency stop function?',
        externalDevices: 'Can external protective devices be connected to the protective stop and emergency stop functions?',
      },
      emergencyStop: {
        everyStation:
          'Does every operator station from which robot motion or other hazardous functions can be started have an emergency stop device?',
        stopsAll: 'Does actuating it stop all robot motion and other hazardous functions in the cell?',
        scope: 'Does the emergency stop act on the whole system, or on defined control zones covering several functions?',
        sameScope: 'Do all emergency stop devices in one working area have the same span of control?',
        scopeInfo: 'Does the information for use describe the span of control of the emergency stop devices?',
        requirements: 'Does the emergency stop function meet the emergency stop requirements of ISO 10218-2?',
        stopCategory: 'Is the emergency stop function of stop category 0 or 1?',
        performance:
          'Does the emergency stop function achieve PL d with a category 3 structure, unless the risk assessment specifies other performance criteria?',
        outputSignal:
          'Where an emergency stop output signal is provided: does it keep working when power is removed from the robot system, or is an emergency stop signal issued otherwise?',
      },
      emergencyRecovery: {
        procedure: 'Does the information for use describe how to move the robot in an emergency, for example to free a trapped person?',
        signs: 'Are signs or markings for this procedure attached to the robot system, or are instructions for it available?',
      },
      warnings: {
        obscured: 'Are warning signs that are obscured replaced by other equally effective warning means?',
      },
      lighting: {
        level: 'Has the lighting level needed for the tasks been determined and stated in the information for use?',
        integral: 'Is integral lighting suitable for the operations provided?',
      },
      applicationHazards: {
        considered: 'Does the integration of the robot system take the hazards of the application into account?',
        interfaces:
          'Are the instructions of the manufacturer on interfaces to other machines, as given in the information for use, followed?',
      },
      enablingDevices: {
        iso10218: 'Do additional enabling devices and their integration meet ISO 10218-1?',
        number: 'Are enough additional enabling devices provided for the number of persons expected in the safeguarded space?',
        sameFunction: 'Do several enabling devices connected to one robot controller have the same functionality?',
        interlocked:
          'Are enabling devices interlocked for those areas of the cell where persons are exposed to hazards from an additional robot or other equipment?',
        restart: 'Do additional interlocked devices require a separate restart?',
      },
      spaces: {
        safeguarded:
          'Is the safeguarded space defined by perimeter safeguarding, with careful consideration of the location, the layout and the hazards there?',
        restricted:
          'Is the restricted space of the robot defined by means that limit the motion of the robot, end-effector, fixtures and workpiece?',
        inside: 'Is the restricted space within the safeguarded space?',
        distance:
          'Is the perimeter safeguarding no closer to the hazard than the restricted space, unless it is designed as a limiting device as described in ISO 10218-2?',
      },
      limitingDevices: {
        mechanical: 'Do mechanical robot limiting devices meet ISO 10218-1?',
        nonMechanical: 'Do non-mechanical robot limiting devices meet ISO 10218-1?',
        controlSystem:
          'Do the control systems of non-mechanical limiting devices meet ISO 10218-1, unless a risk assessment specifies a different performance?',
        stoppingDistance: 'Is the stopping distance at the limiting device included in every calculation of the restricted space?',
        adjusted: 'Are the limiting devices correctly adjusted and secured?',
        actualLoad:
          'Where non-mechanical limiting devices are used, including safety-rated soft axis and space limiting: is the restricted space determined with the robot carrying its actual load?',
        speed:
          'Is the restricted space based on the maximum robot speed or, where the speed is limited by a monitoring system meeting the performance requirements of ISO 10218-2, on the limited speed?',
        information: 'Does the information for use contain the programmed safety-rated and spatial limits?',
        guardStrength:
          'Where the perimeter guard is designed as a limiting device: are the results of the risk assessment used to set the requirements for its design, strength and deformation?',
      },
      dynamicLimiting: {
        stopsRobot: 'Can dynamic mechanical limiting devices stop the robot at rated load and rated speed?',
        performance: 'Do the safety-related parts used for dynamic limiting meet the performance requirements of ISO 10218-2?',
      },
      perimeter: {
        implemented: 'Is the perimeter safeguarding implemented according to the safeguarding requirements of ISO 10218-2?',
        selection:
          'Does the selection of safeguards take into account the expected operating stresses, the influence of the processed material and other relevant external influences?',
        reachOver: 'Do the safety distances against reaching over or through guards meet ISO 13857?',
        interlockedDistance: 'Do the minimum distances of interlocked guards meet ISO 13855?',
        crushing: 'Do the minimum gaps to avoid crushing meet ISO 13854?',
      },
      workingSpace: {
        clearance: 'Is a minimum clearance of 500 mm kept in working areas where manual high speed is used?',
        tasksOutside: 'Where practicable, does the layout allow tasks to be carried out from outside the safeguarded space?',
        safeAccess: 'Is safe and suitable access to work positions inside the safeguarded space provided?',
        accessFree: 'Are the access routes and means of access free of hazards?',
        permanentAccess: 'Is a permanent means of access provided for frequently performed tasks?',
        electricalAccess: 'Where electrical equipment is located above normal reach: is a means of access provided?',
        accessHeight: 'Is access provided to equipment located between 400 mm and 2000 mm above the access level?',
        platforms: 'Are work platforms, walkways, stairs, stepladders and fixed ladders selected and designed to ISO 14122?',
        adjacentCells: 'Are technical protective measures provided between adjacent cells?',
        materialFlow: 'Are technical protective measures provided for adjacent cells during material flow?',
      },
      materialHandling: {
        detection:
          'Are persons detected who enter the hazard zone where material is fed in or removed through the safeguarded space?',
        measures: 'Do protective measures prevent contact with the hazards or bring the hazards into a safe state?',
      },
      processObservation: {
        modes:
          'For process observation inside the safeguarded space: are the manual modes (reduced speed or high speed) or a separate control mode for process observation provided?',
      },
      multiRobot: {
        notSelected: 'Do robot systems in a multi-robot cell that are not selected for operation remain in a safe state?',
        othersSafe: 'Do other robots in the cell that are not under manual control cause no hazard?',
      },
      modeSelection: {
        unauthorised: 'Is unauthorised or unintended selection of the operating mode prevented?',
        selectOnly: 'Do the selection means only select the operating mode and not start operation?',
        separateStart: 'Is a separate action required to start robot operation?',
        indication: 'Is the selected operating mode clearly indicated?',
        changeSafe: 'Does changing the operating mode cause no hazard?',
      },
      automaticMode: {
        entryStops: 'In automatic mode, does entering the safeguarded space trigger a protective stop?',
      },
      automaticSelection: {
        noOverride: 'Does selecting automatic mode not override a protective stop or emergency stop condition?',
        outside: 'Is automatic mode selected from outside the safeguarded space?',
        leavingStops: 'Does switching out of automatic mode cause a stop?',
      },
      automaticStart: {
        outside: 'Is automatic operation started from outside the safeguarded space?',
        safeguardsActive: 'Can automatic operation only be started when all safeguards are active?',
      },
      startRestart: {
        simple: 'Are start and restart simple operations?',
        measuresActive: 'Are the protective measures in operation before start and restart?',
        performance: 'Do the safety-related control functions for start and restart meet the performance requirements of ISO 10218-2?',
        manualReset: 'Are manually operated interlocks (reset) provided for start and restart?',
        personsProtected: 'Are persons inside the safeguarded space protected against start and restart?',
        notFromInside: 'Is it impossible to operate the manual controls for start and restart from inside the safeguarded space?',
        nobodyInside:
          'Are functional safety and protective measures provided that ensure nobody is inside the safeguarded space before start or restart?',
        emergencyStopInside: 'Are accessible emergency stop devices provided inside the safeguarded space?',
        warning: 'Where needed, is a presence detection signal or an audible and visible warning given before start?',
      },
      localControl: {
        local: 'During manual intervention, is the robot under local control in manual mode?',
        observation: 'Does the position of the control device allow the working area to be observed?',
        stopNextToStart: 'Is a stop control placed next to every start control?',
        otherSources: 'Is control from other sources prevented while local control is active?',
      },
      reducedSpeed: {
        tcpOffset: 'Has the tool centre point (TCP) been set using the offset function?',
        maxSpeed: 'Is the maximum speed of the TCP not more than 250 mm/s?',
        slower: 'Has it been determined whether a lower speed is needed?',
        enabling: 'Is a functioning enabling device required for motion?',
      },
      highSpeed: {
        requirements: 'Are the requirements of ISO 10218-1 for manual high speed and for the pendant met?',
        enablingTest: 'Does the information for use include a function test of the enabling device?',
      },
      remoteControl: {
        manualOnly: 'Is remote control only possible in manual mode?',
        oneStation: 'During remote control, is only one operator station active at a time?',
        noOverride: 'Does remote control neither override the local selection nor cause hazardous conditions?',
        activateLocally: 'Can remote control only be activated from the local control?',
        limitParameters: 'Are remote changes to the parameters of the safety-rated soft axis and space limiting restricted?',
        indication: 'Is active remote control indicated?',
        notHighSpeed: 'Is remote control prevented in manual high-speed mode?',
        information: 'Does the information for use contain the requirements for remote manual intervention?',
      },
      pendantGeneral: {
        iso10218: 'Do pendants used inside the safeguarded space meet ISO 10218-1?',
        emergencyStop: 'Does the emergency stop function of the pendant meet the emergency stop requirements of ISO 10218-2?',
        cable: 'Do cabled pendants have sufficient cable length and durability?',
        storage: 'Is storage provided for the pendant to prevent damage?',
      },
      cableless: {
        iso10218: 'Do cableless or detachable pendants meet the requirements of ISO 10218-1?',
        devices: 'Do their emergency stop and enabling devices meet ISO 10218-1?',
        unintended: 'Is unintended control avoided?',
        oneSystem: 'Is a cableless pendant never connected to more than one robot system at a time?',
        signalLoss: 'Does loss of the signal cause a stop, and does restart require a deliberate action?',
        storage:
          'Are disconnection and storage of the pendant arranged so that active and inactive emergency stop devices cannot be confused?',
        exclusive: 'Is exclusive control from one operator station ensured?',
      },
      multiRobotPendant: {
        indication: 'Do pendants for several robots indicate which robots are being controlled?',
        sameMode: 'Are all selected robots in the same operating mode?',
        unselectedSafe: 'Do robots that are not selected pose no hazard?',
        handGuided: 'Do hand-held control elements meet ISO 10218-1?',
      },
      procedures: {
        provided:
          'Are inspection and maintenance procedures provided that take the recommendations of the manufacturer into account and allow continued safe operation?',
        functionTests: 'Does the information for use require periodic function tests of the safety-related equipment?',
      },
      safeAccess: {
        access: 'Is the system designed for safe access for maintenance?',
        energyMeans: 'Does the system have means to control hazardous energy, with details of their use in the information for use?',
        alternative: 'Does the system have suitable alternative safeguards for tasks carried out without isolating the energy?',
      },
      guardDesign: {
        size: 'Are guards that give access large enough for easy access?',
        fixedTool: 'Can fixed guards intended for occasional maintenance and servicing only be removed with a tool?',
        frequentAccess: 'Are points that need frequent access protected by protective devices or, preferably, by movable guards?',
        noStartOnClose: 'Does a movable guard not trigger a start command when it reaches its closed position?',
        remainInside:
          'Where a person can remain inside the safeguarded space with the movable guard closed: are additional protective measures provided?',
        presenceType2:
          'Does presence-sensing equipment used with a restart interlock meet at least the requirements for type 2 of IEC 61496-1?',
      },
      imsHazards: {
        considered: 'Do the risk assessment and the integration take into account hazards from other equipment in the safeguarded space?',
      },
      imsEmergencyStop: {
        allParts: 'Does the IMS have an emergency stop function that acts on all relevant parts of the installation?',
        requirements: 'Do the emergency stop devices meet the emergency stop requirements of ISO 10218-2?',
        scopeInfo: 'Does the information for use describe the span of control of every emergency stop device?',
      },
      imsLocalControl: {
        indicated: 'Is the selection of local control indicated to the control system of the IMS?',
        notOverridden: 'Is it impossible for the IMS to override local control?',
        stopsActive: 'Do the emergency stop and protective stop functions remain operational during local control?',
        nearby: 'Are the means to activate local control located close to the elements controlled?',
        deactivation: 'Does deactivating local control not trigger hazardous situations inside the safeguarded space?',
        confirmation:
          'If local control can be deactivated from inside the safeguarded space: is a separate confirmation from outside the cell required?',
      },
      imsEnabling: {
        requirements: 'Do additional enabling devices in the IMS meet the requirements for additional enabling devices?',
        interlocked: 'Is the enabling device interlocked consistently with the areas of the IMS?',
      },
      imsModes: {
        iso10218: 'Does the mode selection meet ISO 10218-1?',
      },
      imsManual: {
        design: 'Is the IMS designed for safe manual intervention, including a division into zones where needed?',
        iso11161: 'Does the integration of the robot system into the IMS meet ISO 11161?',
      },
      safeguardsGeneral: {
        iso12100: 'Do guards and protective devices meet the requirements of ISO 12100?',
      },
      safeguardSelection: {
        allHazards: 'Does the selection of the perimeter safeguards take all hazards and tasks into account?',
      },
      safeguardInstallation: {
        fixed: 'Are the safeguards permanently installed and correctly positioned?',
      },
      fixedMovableGuards: {
        iso14120: 'Do fixed and movable guards meet ISO 14120?',
        distance: 'Is the minimum distance of the guards from the hazard set according to ISO 13857?',
        accessDistance: 'Where access is prevented by guards: is ISO 13857 applied to set the minimum distance?',
      },
      presenceStart: {
        requirements:
          'Do protective devices with presence sensing that prevent start or restart meet the presence-sensing requirements of ISO 10218-2?',
      },
      presenceClearance: {
        requirements:
          'Do protective devices with presence sensing used to provide a clearance meet the presence-sensing requirements of ISO 10218-2?',
      },
      guards: {
        standards: 'Do all guards meet the applicable requirements of ISO 12100 and ISO 14120?',
        interlocking: 'Do the interlocking devices of guards meet the applicable requirements?',
        fixedTools: 'Can fixed guards only be removed with tools?',
        fixings: 'Where required, do the fixing systems remain attached to the guards or the machine when the guards are removed?',
        notCloser:
          'Is the perimeter safeguarding installed no closer to the hazard than the restricted space, apart from the exceptions in ISO 10218-2?',
      },
      guardDimensions: {
        gaps: 'Do the gap between the lower edge of the guard and the floor, and other openings in the guard, prevent a person from reaching over, under, around or through the guard to the hazard?',
        height: 'Is the guard at least 1400 mm high?',
      },
      interlockedGuards: {
        interlocking: 'Do the interlocking devices of movable guards meet the applicable requirements?',
        closedProtects: 'When closed, do movable guards prevent operators from reaching hazard zones?',
        opening: 'Do movable guards open sideways or away from the hazard, and not into the safeguarded space?',
        safeState: 'Does the interlock bring all hazards into a safe state before an operator can reach them?',
        positioned: 'Are movable guards correctly positioned?',
        controlGuard: 'Do movable guards that start the machine when closed (control guards) meet ISO 14120?',
        performance: 'Does the interlocking function of the movable guards meet at least the performance requirements of ISO 10218-2?',
        resetControls: 'Do the reset controls of movable guards meet the requirements for start and restart?',
      },
      guardLocking: {
        provided: 'Where required, is guard locking provided in addition to the interlock?',
        requirements: 'Does the guard locking meet the guard locking requirements of ISO 10218-2?',
        processParameters:
          'Do process parameters used as a condition for locking and unlocking meet the same functional safety requirements as the interlocking function?',
      },
      entrapment: {
        prevented: 'Does the safeguarded space have a means that prevents a person from being trapped inside?',
      },
      sensitiveEquipment: {
        requirements: 'Do electro-sensitive and pressure-sensitive protective equipment meet the applicable requirements?',
      },
      sensitiveStop: {
        positioned: 'Is sensitive protective equipment that triggers a protective stop correctly positioned?',
        fixed: 'Is it permanently installed and positioned so that operators cannot bypass the detection zone?',
        triggers:
          'Is a protective stop triggered when the sensitive protective equipment is actuated during a hazardous machine function?',
        noMotion:
          'After it has been actuated, do the hazardous machine functions it protects cause no hazardous motion or situation until it is reset?',
        resetNoStart: 'Does resetting the sensitive protective equipment alone not start hazardous machine functions?',
        distanceFormula:
          'Is the minimum distance of the sensitive protective equipment calculated with the safety distance formula for every direction of approach, using the maximum reach of the moving parts in that direction?',
        partlyInside: 'If an operator can remain partly inside the safeguarded space: are additional measures taken to avoid hazardous situations?',
        resetVisibility:
          'If an operator inside might not be seen from the reset control: are additional measures taken to prevent the restart interlock from being reset?',
        deliberateReset: 'Does resetting the restart interlock require a deliberate action by a person?',
      },
      presenceSensing: {
        combined: 'Is presence-sensing equipment that prevents a start used together with other protective measures?',
        wholeZone: 'Is it arranged and configured so that a person, or part of a person, is detected throughout the detection zone?',
        noBypass: 'Where needed, are additional measures taken so that the detection zone cannot be bypassed?',
      },
      manualStations: {
        noFurtherHazards:
          'Are measures provided so that operators are not exposed to further hazards from operating manual material handling stations?',
        applicationHazards: 'Are measures taken so that the operator is not exposed to hazards of the application?',
      },
      movingStations: {
        motionHazards: 'Are measures taken to protect the operator from hazards caused by movements of the manual stations?',
        gap: 'Is the gap between a moving station and fixed elements not more than 120 mm?',
      },
      sharedWorkspace: {
        coverage:
          'Where presence sensing detects the operator in the shared workspace: does the detection zone cover the whole shared workspace?',
        unintendedReset: 'Where a restart interlock is provided in a shared workspace: are measures provided against unintended resetting?',
        visibleReset:
          'Where manual reset is used in a shared workspace: can the whole workspace be seen from the reset position, or are other measures taken?',
      },
      openings: {
        dimensions: 'Do the openings for feeding and removing material have the minimum dimensions required?',
        crushing: 'Are crushing and shearing hazards between the material and the sides of the openings prevented?',
        access: 'Is access to the hazard through the openings prevented or detected?',
        muting:
          'Do electro-sensitive protective devices let the material pass by muting or by a change of the detection zone, for example blanking?',
        mutingStandard: 'Does the muting function meet ISO 13849-1?',
        mutingLevel:
          'Do muting and changes of the detection zone, for example blanking, achieve at least the functional safety level that the risk assessment specifies for the electro-sensitive protective device?',
      },
      adjacentCells: {
        measures:
          'Are measures provided that prevent operators from reaching hazards in adjacent cells or that bring these hazards to a stop?',
        height: 'Are fixed guards that prevent access to hazards in adjacent cells at least 1400 mm high?',
        otherMeasures: 'Are measures other than fixed guards selected on the basis of the risk assessment required by ISO 10218-2?',
        suspended: 'Do measures that are suspended for production operations meet the functional safety level specified in the risk assessment?',
      },
      endEffectors: {
        energyLoss: 'Are end-effectors and tool changers designed and built so that loss or restoration of power causes no hazard?',
        misuse: 'Is the tool changer designed so that misuse cannot cause a hazardous situation?',
        position: 'Is a tool change only possible in the tool change position?',
        loads: 'Does the tool changer withstand the expected static and dynamic loads?',
      },
      muting: {
        limited: 'Is muting limited to processes where it is essential?',
        noUndetected: 'When muting has ended, is it impossible for a person to remain undetected in the hazard zone?',
        automatic: 'Is muting started and ended automatically, provided the muting conditions are correct?',
        equivalentLevel: 'Does the muting function achieve a safety performance equivalent to that of the muted function?',
        noDegradation: 'Does the performance level of the muting function not degrade the performance level of the protective function?',
        failure: 'If the muting function fails, is further muting prevented until the fault is cleared?',
        information: 'Does the information for use describe the muting devices, their location, the areas covered and their function?',
      },
      suspension: {
        dedicatedMode: 'Do tasks that require suspending safeguards have a dedicated operating mode?',
        lockableSelection: 'Is this mode selected by means that can be secured, for example a lockable selector switch?',
        automaticRequirements: 'Where safeguards are suspended automatically: are the requirements of ISO 10218-2 for automatic suspension met?',
        othersStopped:
          'Where safeguards are suspended automatically: is equipment not needed for the task in a protective stop or under the direct control of the operator?',
        criticalSituations: 'Does the information for use describe the critical situations in which safeguards must be suspended manually?',
      },
      collaborativeInfo: {
        safeguardsModes: 'Does the information for use describe the protective devices and the mode selection needed for collaborative operation?',
      },
      collaborativeRisk: {
        riskAssessment: 'Has the integrator carried out a risk assessment that covers the whole collaborative workspace?',
        robots: 'Do the robots in the collaborative workspace meet ISO 10218-1?',
        presenceDevices: 'Do protective devices used for presence detection meet the performance requirements of ISO 10218-2?',
        additionalDevices: 'Do additional protective devices in the collaborative workspace meet the performance requirements of ISO 10218-2?',
        progression:
          'Are technical protective measures designed and installed so that they prevent or detect a person moving further into the cell beyond the collaborative workspace?',
        stopBeyond: 'Does the robot stop, and do the hazards end, when someone enters the safeguarded space beyond the collaborative workspace?',
        nonCollaborativeAccess:
          'Does the perimeter safeguarding prevent or detect access to the part of the safeguarded space not intended for collaborative operation?',
        otherMachines:
          'Do other connected machines with safety functions in the collaborative workspace meet the performance requirements of ISO 10218-2, unless the risk assessment specifies otherwise?',
      },
      collaborativeWorkspace: {
        defined:
          'Is the collaborative workspace, in which persons work directly with the robot, clearly marked, for example by floor markings or signs?',
        parameters: 'Do the robot parameters, together with the protective devices, meet the performance requirements of ISO 10218-2?',
        severalPersons:
          'If several persons take part in collaborative operation: is each person protected by control functions that meet the performance requirements of ISO 10218-2?',
        easyTasks: 'Does the collaborative workspace allow the tasks to be carried out easily?',
        equipmentPosition: 'Does the position of the equipment cause no additional hazards?',
        clearance: 'Are additional protective measures in place against trapping and crushing in areas with less than 500 mm clearance?',
      },
      collaborativeTransition: {
        safe: 'Does changing from autonomous to collaborative operation and back not endanger persons?',
      },
      collaborativeFeatures: {
        selected: 'Are suitable safety features for collaborative robot operation selected?',
        failureStop: 'Does a detected failure of a selected safety feature lead to a protective stop?',
        restart:
          'After a detected failure, can autonomous operation only resume after a deliberate restart action from outside the collaborative workspace?',
      },
      monitoredStop: {
        stops:
          'With a safety-rated monitored stop: does the robot stop as soon as a person enters the collaborative workspace, and does it hold a safety-rated monitored stop?',
      },
      handGuiding: {
        handoverStop: 'When the robot reaches the hand-over position for hand guiding: is a safety-rated monitored stop issued?',
        device: 'Does the hand-guiding device meet ISO 10218-1?',
        releaseStop: 'When the operator releases the hand-guiding device: is a safety-rated monitored stop triggered?',
      },
      speedSeparation: {
        robots: 'With speed and separation monitoring: do the robots in the collaborative workspace meet ISO 10218-1?',
        parameters: 'Are the parameters set on the basis of the risk assessment, with guidance from ISO/TS 15066?',
      },
      powerForce: {
        robots: 'With power and force limiting: do the robots in the collaborative workspace meet ISO 10218-1?',
        parameters: 'Are the parameters set on the basis of the risk assessment, with guidance from ISO/TS 15066?',
      },
      commissioningConcept: {
        interimSafeguards: 'Does the commissioning concept describe the protective measures (interim safeguards) needed during commissioning?',
      },
      interimSafeguarding: {
        protects: 'Do the interim safeguards protect against the hazards identified in the risk assessment?',
        barriers: 'Are at least warning barriers installed to mark the restricted space?',
        documented: 'Are the interim safeguards described in the information for use?',
      },
      startUp: {
        plan: 'Does the plan for the initial start-up cover at least the points listed in ISO 10218-2?',
      },
    },
    hints: {},
  },
}
