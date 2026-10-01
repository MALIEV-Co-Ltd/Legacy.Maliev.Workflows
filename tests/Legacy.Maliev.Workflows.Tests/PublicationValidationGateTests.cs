using System.Diagnostics;
using YamlDotNet.RepresentationModel;
using Xunit;

namespace Legacy.Maliev.Workflows.Tests;

public sealed class PublicationValidationGateTests
{
    [Fact]
    public void Publisher_BeforeCloudAuthentication_RequiresExactCommitValidation()
    {
        YamlMappingNode workflow = Workflow();
        YamlMappingNode permissions = (YamlMappingNode)workflow.Children[new YamlScalarNode("permissions")];
        Assert.Equal("read", Scalar(permissions, "actions"));
        Assert.False(permissions.Children.ContainsKey(new YamlScalarNode("id-token")));
        YamlMappingNode jobs = (YamlMappingNode)workflow.Children[new YamlScalarNode("jobs")];
        YamlMappingNode prerequisite = (YamlMappingNode)jobs.Children[new YamlScalarNode("validation")];
        Assert.False(((YamlMappingNode)prerequisite.Children[new YamlScalarNode("permissions")]).Children.ContainsKey(new YamlScalarNode("id-token")));
        Assert.Equal("validation", Scalar((YamlMappingNode)jobs.Children[new YamlScalarNode("publish")], "needs"));
        YamlMappingNode[] steps = Steps(workflow);
        int gate = Array.FindIndex(steps, step => Scalar(step, "name") == "Verify exact protected-main validation");
        int cloud = Array.FindIndex(steps, step => Scalar(step, "id") == "auth");
        Assert.True(gate >= 0 && gate < cloud);
        int push = Array.FindIndex(steps, step => Scalar(step, "id") == "publish");
        Assert.Equal("Verify exact protected-main validation", Scalar(steps[cloud - 1], "name"));
        Assert.Equal("Verify exact protected-main validation", Scalar(steps[push - 1], "name"));
        Assert.Equal(3, steps.Count(step => Scalar(step, "name") == "Verify exact protected-main validation"));
        YamlMappingNode checkout = steps.Single(step => Scalar(step, "name") == "Check out caller repository");
        Assert.Equal("${{ github.sha }}", Scalar((YamlMappingNode)checkout.Children[new YamlScalarNode("with")], "ref"));
        Assert.Contains("git rev-parse HEAD", Scalar(steps.Single(step => Scalar(step, "name") == "Verify caller checkout identity"), "run"), StringComparison.Ordinal);
        Assert.False(steps[gate].Children.ContainsKey(new YamlScalarNode("continue-on-error")));
        Assert.Equal("python", Scalar(steps[gate], "shell"));
        YamlMappingNode environment = (YamlMappingNode)steps[gate].Children[new YamlScalarNode("env")];
        Assert.Equal("${{ github.token }}", Scalar(environment, "GH_TOKEN"));
    }

    [Theory]
    [InlineData("success", true)]
    [InlineData("paged_jobs", true)]
    [InlineData("missing", false)]
    [InlineData("pending", false)]
    [InlineData("failure", false)]
    [InlineData("old_success_new_pending", false)]
    [InlineData("wrong_sha", false)]
    [InlineData("wrong_repo", false)]
    [InlineData("pull_request", false)]
    [InlineData("wrong_path", false)]
    [InlineData("inactive_workflow", false)]
    [InlineData("skipped_job", false)]
    [InlineData("empty_jobs", false)]
    [InlineData("stale_attempt", false)]
    [InlineData("wrong_job_attempt", false)]
    [InlineData("api_error", false)]
    [InlineData("invalid_json", false)]
    [InlineData("missing_required_job", false)]
    [InlineData("duplicate_required_job", false)]
    [InlineData("wrong_reference", false)]
    [InlineData("changed_attempt", false)]
    [InlineData("new_run_after_jobs", false)]
    [InlineData("second_page_failed_job", false)]
    [InlineData("pagination_limit", false)]
    [InlineData("final_failure", false)]
    [InlineData("final_wrong_sha", false)]
    [InlineData("older_failed_rerun", false)]
    [InlineData("wrong_job_sha", false)]
    public async Task ActualTrustedStep_WhenApiEvidenceIsEvaluated_FailsClosed(string scenario, bool accepted)
    {
        string script = Scalar(Steps(Workflow()).First(step => Scalar(step, "name") == "Verify exact protected-main validation"), "run");
        string temporary = Path.Combine(Path.GetTempPath(), "publication-ci-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporary);
        try
        {
            string harness = Path.Combine(temporary, "fixture.py");
            await File.WriteAllTextAsync(harness, Harness, TestContext.Current.CancellationToken);
            ProcessStartInfo start = new(OperatingSystem.IsWindows() ? "python" : "python3")
            {
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                WorkingDirectory = temporary,
            };
            start.ArgumentList.Add(harness);
            start.ArgumentList.Add(scenario);
            start.Environment["ACTUAL_GATE_SOURCE"] = script;
            using Process process = Process.Start(start)!;
            Task<string> output = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
            Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
            await process.WaitForExitAsync(TestContext.Current.CancellationToken);
            string combined = await output + await error;
            Assert.Equal(accepted ? 0 : 1, process.ExitCode);
            Assert.Contains(accepted ? "publication_validation_verified" : "publication_validation_unavailable", combined, StringComparison.Ordinal);
            Assert.DoesNotContain("fixture-token-value", combined, StringComparison.Ordinal);
            Assert.DoesNotContain("sensitive-api-message", combined, StringComparison.Ordinal);
        }
        finally
        {
            Directory.Delete(temporary, recursive: true);
        }
    }

    private static YamlMappingNode Workflow()
    {
        YamlStream yaml = new();
        yaml.Load(new StringReader(File.ReadAllText(Path.Combine(RepositoryContractTests.FindRepositoryRoot(), ".github/workflows/publish-image.yml"))));
        return (YamlMappingNode)yaml.Documents.Single().RootNode;
    }

    private static YamlMappingNode[] Steps(YamlMappingNode workflow) =>
        ((YamlSequenceNode)((YamlMappingNode)((YamlMappingNode)workflow.Children[new YamlScalarNode("jobs")])
            .Children[new YamlScalarNode("publish")]).Children[new YamlScalarNode("steps")])
        .Children.Cast<YamlMappingNode>().ToArray();

    private static string Scalar(YamlMappingNode node, string name) =>
        node.Children.TryGetValue(new YamlScalarNode(name), out YamlNode? value) ? ((YamlScalarNode)value).Value ?? "" : "";

    private const string Harness = """
        import copy, io, json, os, sys, urllib.parse, urllib.request
        from unittest.mock import patch
        scenario = sys.argv[1]
        repository = 'MALIEV-Co-Ltd/Legacy.Maliev.Fixture'
        sha = 'a' * 40
        os.environ.update(GITHUB_REPOSITORY=repository, GITHUB_SHA=sha, GH_TOKEN='fixture-token-value')
        workflow = {'id': 77, 'path': '.github/workflows/ci-main.yml', 'state': 'active'}
        run = {'id': 101, 'run_number': 8, 'run_attempt': 2, 'workflow_id': 77,
               'path': '.github/workflows/ci-main.yml', 'head_sha': sha, 'head_branch': 'main',
               'event': 'push', 'status': 'completed', 'conclusion': 'success',
               'head_repository': {'full_name': repository}, 'repository': {'full_name': repository},
               'referenced_workflows': [{'path': repository + '/.github/workflows/_build-and-test.yml@' + sha, 'sha': sha}]}
        jobs = [{'id': 201, 'name': 'validate / validate', 'run_attempt': 2, 'run_id': 101,
                 'head_sha': sha, 'status': 'completed', 'conclusion': 'success'}]
        runs = [copy.deepcopy(run)]
        if scenario == 'missing': runs = []
        if scenario in ('pending', 'old_success_new_pending'): run.update(status='in_progress', conclusion=None)
        if scenario == 'failure': run['conclusion'] = 'failure'
        if scenario == 'wrong_sha': run['head_sha'] = 'b' * 40
        if scenario == 'wrong_repo': run['head_repository']['full_name'] = 'untrusted/fork'
        if scenario == 'pull_request': run['event'] = 'pull_request'
        if scenario == 'wrong_path': workflow['path'] = '.github/workflows/unrelated.yml'
        if scenario == 'inactive_workflow': workflow['state'] = 'disabled_manually'
        if scenario == 'skipped_job': jobs[0]['conclusion'] = 'skipped'
        if scenario == 'empty_jobs': jobs = []
        if scenario == 'stale_attempt': run['run_attempt'] = 1
        if scenario == 'wrong_job_attempt': jobs[0]['run_attempt'] = 1
        if scenario == 'missing_required_job': jobs[0]['name'] = 'unrelated'
        if scenario == 'duplicate_required_job': jobs.append(dict(jobs[0], id=202))
        if scenario == 'wrong_reference': run['referenced_workflows'][0]['sha'] = 'b' * 40
        if scenario == 'older_failed_rerun': runs.append(dict(run, id=99, run_number=7, run_attempt=3, conclusion='failure'))
        if scenario == 'wrong_job_sha': jobs[0]['head_sha'] = 'b' * 40
        if scenario == 'old_success_new_pending':
            runs.append(dict(run, id=102, run_number=9))
            run.update(id=102, run_number=9)
        run_reads = 0
        run_list_reads = 0
        def fetch(request, timeout):
            global run_reads, run_list_reads
            assert timeout == 20
            assert request.get_header('Authorization') == 'Bearer fixture-token-value'
            url = urllib.parse.urlparse(request.full_url)
            assert url.scheme == 'https' and url.netloc == 'api.github.com'
            assert url.path.startswith('/repos/' + repository + '/actions/')
            if scenario == 'api_error': raise OSError('sensitive-api-message fixture-token-value')
            if scenario == 'invalid_json': return io.BytesIO(b'sensitive-api-message')
            query = urllib.parse.parse_qs(url.query)
            page = int(query.get('page', ['1'])[0])
            if url.path.endswith('/workflows/ci-main.yml'): result = workflow
            elif url.path.endswith('/workflows/77/runs'):
                assert query['head_sha'] == [sha] and query['event'] == ['push'] and query['branch'] == ['main']
                run_list_reads += 1
                if scenario == 'new_run_after_jobs' and run_list_reads > 1:
                    runs.append(dict(run, id=102, run_number=9, status='in_progress', conclusion=None))
                if scenario == 'final_failure' and run_list_reads > 1: runs[0]['conclusion'] = 'failure'
                if scenario == 'final_wrong_sha' and run_list_reads > 1: runs[0]['head_sha'] = 'b' * 40
                if scenario == 'pagination_limit': return io.BytesIO(json.dumps({'workflow_runs': [dict(run, id=100+i, run_number=i+1) for i in range(100)]}).encode())
                result = {'workflow_runs': runs if page == 1 else []}
            elif url.path.endswith('/runs/101') or url.path.endswith('/runs/102'):
                run_reads += 1
                result = dict(run, run_attempt=3) if scenario == 'changed_attempt' and run_reads > 1 else run
            elif url.path.endswith('/attempts/2/jobs'):
                if scenario in ('paged_jobs', 'second_page_failed_job'):
                    first = [jobs[0]] + [dict(jobs[0], id=201+i, name='extra-' + str(i)) for i in range(1, 100)]
                    last = [dict(jobs[0], id=301, name='last', conclusion='failure' if scenario == 'second_page_failed_job' else 'success')]
                    result = {'jobs': first if page == 1 else last}
                else: result = {'jobs': jobs if page == 1 else []}
            else: raise AssertionError('Unexpected API request')
            return io.BytesIO(json.dumps(result).encode())
        with patch.object(urllib.request, 'urlopen', fetch):
            exec(compile(os.environ['ACTUAL_GATE_SOURCE'], '<actual-workflow-gate>', 'exec'), {'__name__': '__main__'})
        """;
}
