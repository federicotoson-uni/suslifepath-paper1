function paper1_catalogue_scale(input_json, output_csv)
%PAPER1_CATALOGUE_SCALE  Batch DGP (ECOB-proxy collective) over N missions.
%
%  Catalogue-scale companion to paper0_ecob_proxy_single.m: loads the
%  Celestrak population ONCE, computes the reference collective probability
%  ONCE, then loops over an array of N missions read from INPUT_JSON,
%  writing DGP = P_col/P_col_ref per mission to OUTPUT_CSV.
%
%  INPUT_JSON: array of objects, each with fields
%    altitude_km, inclination_deg, eccentricity,
%    op_lifetime_yr, residual_lifetime_yr,
%    exposed_surface_m2, total_surface_m2
%  OUTPUT_CSV: header "index,DGP" then one row per mission (1-based index).
%
%  Author: Federico Toson. Reuses Paper 0 collective_probability + the same
%  reference mission as paper0_ecob_proxy_single.m (consistency).

    PAPER1_DIR  = fileparts(mfilename('fullpath'));
    REPO_PARENT = fileparts(fileparts(PAPER1_DIR));
    CANDIDATES = { ...
        fullfile(REPO_PARENT, 'suslifepath-paper0', 'code'), ...
        fullfile(REPO_PARENT, 'Paper0_SimplifiedAlgorithm', 'code') };
    PAPER0_DIR = '';
    for k = 1:numel(CANDIDATES)
        if exist(fullfile(CANDIDATES{k}, 'collective_probability.m'), 'file')
            PAPER0_DIR = CANDIDATES{k}; break;
        end
    end
    if isempty(PAPER0_DIR)
        error('paper1_catalogue_scale:NoPaper0', 'Paper 0 modules not found.');
    end
    addpath(PAPER0_DIR);
    DATA_DIR = fullfile(fileparts(PAPER0_DIR), 'data');

    raw = fileread(input_json);
    M = jsondecode(raw);
    if isstruct(M), M = num2cell(M); end   % normalise to cell array of structs

    CSV_ACTIVE = fullfile(DATA_DIR, 'celestrak_active.csv');
    CSV_DEBRIS = fullfile(DATA_DIR, 'celestrak_debris.csv');
    PopulationData = databasecreator_real(CSV_ACTIVE, Inf, CSV_DEBRIS);

    rearth = 6378;
    ref_m  = struct('yol',2020,'lt',7,'dt',25,'it',0.2,'r',7078, ...
        'ecc',0.001,'w',0,'ra',0,'inc',98,'pl','G','net',0,'man','U','cost',1e8);
    ref_sc = struct('ex_surf',5,'tot_surf',15,'rho',500);
    S_ref  = ref_sc.tot_surf;
    [P_col_ref, ~] = collective_probability(PopulationData, ref_m, ref_sc, S_ref);
    P_col_ref = max(P_col_ref, eps);

    N = numel(M);
    DGP = zeros(N,1);
    for i = 1:N
        if iscell(M), in = M{i}; else, in = M(i); end
        m = struct('yol',2020,'lt',in.op_lifetime_yr,'dt',in.residual_lifetime_yr, ...
            'it',0.2,'r',in.altitude_km + rearth,'ecc',in.eccentricity, ...
            'w',0,'ra',0,'inc',in.inclination_deg,'pl','G','net',0,'man','U','cost',1e8);
        sc = struct('ex_surf',in.exposed_surface_m2,'tot_surf',in.total_surface_m2,'rho',500);
        [P_col, ~] = collective_probability(PopulationData, m, sc, S_ref);
        DGP(i) = P_col / P_col_ref;
    end

    fid = fopen(output_csv, 'w');
    fprintf(fid, 'index,DGP\n');
    for i = 1:N
        fprintf(fid, '%d,%.6e\n', i, DGP(i));
    end
    fclose(fid);
    fprintf('paper1_catalogue_scale: %d missions -> %s\n', N, output_csv);
end
