function paper0_ecob_proxy_single(input_json, output_csv)
%PAPER0_ECOB_PROXY_SINGLE  Single-mission ECOB-proxy wrapper for the SSCI toolchain.
%
%  Callable from Python (via code/matlab_bridge.py call_matlab).
%  Reads mission parameters from INPUT_JSON and writes a CSV summary to
%  OUTPUT_CSV with the metric,value rows expected by the orchestrator.
%
%  Expected INPUT_JSON fields:
%    altitude_km           altitude of perigee [km]
%    inclination_deg       orbit inclination [deg]
%    eccentricity          orbit eccentricity [-]
%    op_lifetime_yr        operational lifetime [yr]
%    residual_lifetime_yr  post-mission residual lifetime [yr]
%    mass_kg               spacecraft dry mass [kg]
%    cross_section_m2      collision cross-section [m^2]
%    exposed_surface_m2    exposed surface area [m^2]
%    total_surface_m2      total surface area [m^2]
%    cost_usd              replacement cost [USD]
%
%  OUTPUT_CSV format:
%    metric,value
%    P_ind,...      individual collision probability over T_op
%    P_col,...      collective severity proxy (debris generation potential)
%    P_eco,...      snapshot-ECOB proxy (mass-based, T_eco=200 yr)
%    DGP,...        adopted = P_col here (SSCI orbital debris component)
%
%  Author: Federico Toson
%  Dependencies: Paper 0 modules (collective_probability.m,
%                individual_probability_flux.m, ecob_proxy.m,
%                databasecreator_real.m). The Paper 0 repo path is
%                resolved automatically below.

    % --- Resolve Paper 0 repo path ----------------------------------- %
    % First try the local Zenodo-synced repo, then fall back to the
    % working copy in PAPER_SusLifePath_2026/Paper0_SimplifiedAlgorithm.
    PAPER1_DIR  = fileparts(mfilename('fullpath'));
    REPO_PARENT = fileparts(fileparts(PAPER1_DIR));     % .../PAPER_SusLifePath_2026
    CANDIDATES = { ...
        fullfile(REPO_PARENT, 'suslifepath-paper0', 'code'), ...
        fullfile(REPO_PARENT, 'Paper0_SimplifiedAlgorithm', 'code') ...
    };
    PAPER0_DIR = '';
    for k = 1:numel(CANDIDATES)
        if exist(fullfile(CANDIDATES{k}, 'collective_probability.m'), 'file')
            PAPER0_DIR = CANDIDATES{k};
            break;
        end
    end
    if isempty(PAPER0_DIR)
        error('paper0_ecob_proxy_single:NoPaper0', ...
              'Could not locate Paper 0 modules in any of: %s', ...
              strjoin(CANDIDATES, ' | '));
    end
    addpath(PAPER0_DIR);
    DATA_DIR = fullfile(fileparts(PAPER0_DIR), 'data');

    % --- Load inputs -------------------------------------------------- %
    fid = fopen(input_json, 'r');
    if fid < 0
        error('Could not open input JSON: %s', input_json);
    end
    raw = fread(fid, Inf, 'char=>char')';
    fclose(fid);
    in = jsondecode(raw);

    % --- Build population (Celestrak May 2026 snapshot from Paper 0) -- %
    CSV_ACTIVE = fullfile(DATA_DIR, 'celestrak_active.csv');
    CSV_DEBRIS = fullfile(DATA_DIR, 'celestrak_debris.csv');
    PopulationData = databasecreator_real(CSV_ACTIVE, Inf, CSV_DEBRIS);

    % --- Mission struct in Paper 0 format ----------------------------- %
    rearth = 6378;
    m = struct( ...
        'yol',  2020, ...
        'lt',   in.op_lifetime_yr, ...
        'dt',   in.residual_lifetime_yr, ...
        'it',   0.2, ...
        'r',    in.altitude_km + rearth, ...
        'ecc',  in.eccentricity, ...
        'w',    0, ...
        'ra',   0, ...
        'inc',  in.inclination_deg, ...
        'pl',   'G', ...
        'net',  0, ...
        'man',  'U', ...
        'cost', in.cost_usd);
    sc = struct( ...
        'ex_surf',  in.exposed_surface_m2, ...
        'tot_surf', in.total_surface_m2, ...
        'rho',      500);

    % --- Reference mission (SAME as Paper 0 normalisation) ----------- %
    ref_m  = struct('yol',2020,'lt',7,'dt',25,'it',0.2,'r',7078, ...
        'ecc',0.001,'w',0,'ra',0,'inc',98,'pl','G','net',0,'man','U', ...
        'cost',1e8);
    ref_sc = struct('ex_surf',5,'tot_surf',15,'rho',500);
    S_ref  = ref_sc.tot_surf;
    M_ref  = 500;   % reference smallsat mass [kg]

    [P_ind_ref, ~] = individual_probability_flux(PopulationData, ref_m, ref_sc);
    [P_col_ref, ~] = collective_probability(PopulationData, ref_m, ref_sc, S_ref);
    [P_eco_ref, ~] = ecob_proxy(PopulationData, ref_m, ref_sc, M_ref, M_ref);

    % --- Mission scores ----------------------------------------------- %
    [P_ind, ~] = individual_probability_flux(PopulationData, m, sc);
    [P_col, ~] = collective_probability(PopulationData, m, sc, S_ref);
    [P_eco, ~] = ecob_proxy(PopulationData, m, sc, M_ref, in.mass_kg);

    % --- Normalised forms (multiples of reference) -------------------- %
    R_ind = (P_ind * in.cost_usd) / max(P_ind_ref * ref_m.cost, eps);
    R_col = P_col / max(P_col_ref, eps);
    R_eco = P_eco / max(P_eco_ref, eps);

    % --- DGP adopted = R_col (orbital debris component of SSCI) ------ %
    DGP = R_col;

    % --- Write CSV ---------------------------------------------------- %
    fid = fopen(output_csv, 'w');
    if fid < 0
        error('Could not open output CSV: %s', output_csv);
    end
    fprintf(fid, 'metric,value\n');
    fprintf(fid, 'P_ind,%.6e\n',  P_ind);
    fprintf(fid, 'P_col,%.6e\n',  P_col);
    fprintf(fid, 'P_eco,%.6e\n',  P_eco);
    fprintf(fid, 'R_ind,%.6e\n',  R_ind);
    fprintf(fid, 'R_col,%.6e\n',  R_col);
    fprintf(fid, 'R_eco,%.6e\n',  R_eco);
    fprintf(fid, 'DGP,%.6e\n',    DGP);
    fclose(fid);

    fprintf('paper0_ecob_proxy_single: written %s\n', output_csv);
end
