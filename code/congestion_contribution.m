function congestion_contribution(input_json, output_csv)
%CONGESTION_CONTRIBUTION  Computes the Congestion Contribution (CC) of a
%mission for the SSCI Paper 1.
%
%  Formula (Paper 1 Section 3.2.2):
%      CC_m = integral V_occ(h) * rho_op(h,t) dt    over [t0, t0+T_op]
%
%  where:
%    V_occ      = operational exclusion volume around the spacecraft
%                 (ECSS-U-AS-10C conjunction-analysis keep-out box)
%    rho_op     = operational population density at mission altitude
%                 (Celestrak May 2026 snapshot from Paper 0)
%    T_op       = operational lifetime [yr]
%
%  Distinct from DGP (debris generation potential): CC counts the
%  satellite's contribution to operational congestion DURING service,
%  while DGP counts long-term debris generation AFTER service.
%
%  Snapshot assumption: rho_op is taken constant over T_op (no
%  population evolution). The integral collapses to V_occ * rho_op * T_op
%  with units of "satellite-year exposure" (sat * km^-3 * km^3 * yr).
%
%  Inputs (input_json keys):
%    altitude_km            mission altitude [km]
%    op_lifetime_yr         operational lifetime [yr]
%    cross_section_m2       spacecraft cross-section [m^2]   (informational)
%
%  Output (output_csv): metric,value rows for
%    CC                     raw CC score [sat * yr]
%    rho_op_per_km3         resident operational density [sat/km^3]
%    V_occ_km3              adopted keep-out volume [km^3]
%    T_op_yr                operational lifetime [yr]
%    N_in_shell             active satellites in ±25 km shell at h
%    V_shell_km3            shell volume [km^3]
%
%  Author: Federico Toson
%  References:
%    Paper 1 Section 3.2.2 (Congestion Contribution definition)
%    Paper 0 (Toson 2026) — Celestrak snapshot and density formulation
%    ECSS-U-AS-10C (2024) — Space Sustainability Standard, keep-out box

    % --- Resolve Paper 0 modules path (same pattern as ecob_proxy_single) --
    PAPER1_DIR  = fileparts(mfilename('fullpath'));
    REPO_PARENT = fileparts(fileparts(PAPER1_DIR));
    CANDIDATES = { ...
        fullfile(REPO_PARENT, 'suslifepath-paper0', 'code'), ...
        fullfile(REPO_PARENT, 'Paper0_SimplifiedAlgorithm', 'code') ...
    };
    PAPER0_DIR = '';
    for k = 1:numel(CANDIDATES)
        if exist(fullfile(CANDIDATES{k}, 'databasecreator_real.m'), 'file')
            PAPER0_DIR = CANDIDATES{k};
            break;
        end
    end
    if isempty(PAPER0_DIR)
        error('congestion_contribution:NoPaper0', ...
              'Could not locate Paper 0 modules in: %s', ...
              strjoin(CANDIDATES, ' | '));
    end
    addpath(PAPER0_DIR);
    DATA_DIR = fullfile(fileparts(PAPER0_DIR), 'data');

    % --- Load mission inputs ----------------------------------------- %
    fid = fopen(input_json, 'r');
    if fid < 0
        error('Could not open input JSON: %s', input_json);
    end
    raw = fread(fid, Inf, 'char=>char')';
    fclose(fid);
    in = jsondecode(raw);

    % --- Load Celestrak active satellites (operational pop) ---------- %
    CSV_ACTIVE = fullfile(DATA_DIR, 'celestrak_active.csv');
    CSV_DEBRIS = fullfile(DATA_DIR, 'celestrak_debris.csv');
    PopulationData = databasecreator_real(CSV_ACTIVE, Inf, CSV_DEBRIS);

    % --- Operational population density at mission altitude ---------- %
    rearth = 6378;                                       % [km]
    h_mission = in.altitude_km;                          % [km]

    % Only active satellites (LEO + GEO + OTH), no debris — CC quantifies
    % contribution to OPERATIONAL congestion, not to debris hazard.
    ACTIVE = [PopulationData.LEO; PopulationData.GEO; PopulationData.OTH];
    h_active = ACTIVE(:,1) - rearth;                     % perigee alt [km]

    % Density in a ±dh shell around mission altitude
    dh = 25;                                             % [km], matches Paper 0 binning
    mask = abs(h_active - h_mission) <= dh;
    N_in_shell = sum(mask);

    % Spherical shell volume: 4*pi*r^2 * 2*dh
    r_shell = rearth + h_mission;                        % [km]
    V_shell = 4 * pi * r_shell^2 * (2 * dh);             % [km^3]
    rho_op  = N_in_shell / V_shell;                      % [sat/km^3]

    % --- Operational exclusion volume (keep-out box) ----------------- %
    % ECSS-U-AS-10C conjunction-analysis convention: ±25 km cross-track,
    % ±25 km radial, ±25 km along-track => (50 km)^3 cube.
    L_keepout_km = 25;
    V_occ = (2 * L_keepout_km)^3;                        % [km^3]

    % --- Time integration over operational lifetime ------------------ %
    T_op_yr = in.op_lifetime_yr;
    CC = V_occ * rho_op * T_op_yr;   % [sat * yr]

    % --- Write CSV --------------------------------------------------- %
    fid = fopen(output_csv, 'w');
    if fid < 0
        error('Could not open output CSV: %s', output_csv);
    end
    fprintf(fid, 'metric,value\n');
    fprintf(fid, 'CC,%.6e\n',             CC);
    fprintf(fid, 'rho_op_per_km3,%.6e\n', rho_op);
    fprintf(fid, 'V_occ_km3,%.6e\n',      V_occ);
    fprintf(fid, 'T_op_yr,%.6e\n',        T_op_yr);
    fprintf(fid, 'N_in_shell,%d\n',       N_in_shell);
    fprintf(fid, 'V_shell_km3,%.6e\n',    V_shell);
    fclose(fid);

    fprintf('congestion_contribution: written %s (CC = %.3e sat*yr)\n', ...
            output_csv, CC);
end
