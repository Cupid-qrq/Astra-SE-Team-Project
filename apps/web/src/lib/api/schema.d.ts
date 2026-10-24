export interface paths {
    "/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getSession
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getSession"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * login
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * logout
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * changePassword
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["changePassword"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/courses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listCourses
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listCourses"];
        put?: never;
        /**
         * createCourse
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createCourse"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/courses/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getCourse
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getCourse"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * updateCourse
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updateCourse"];
        trace?: never;
    };
    "/courses/{id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listMembers
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listMembers"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/courses/{id}/members/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * updateMember
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        put: operations["updateMember"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/courses/{id}/problems": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listProblems
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listProblems"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problems": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * createProblem
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createProblem"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * createVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getVersion"];
        put?: never;
        post?: never;
        /**
         * deleteVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        delete: operations["deleteVersion"];
        options?: never;
        head?: never;
        /**
         * updateVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updateVersion"];
        trace?: never;
    };
    "/problem-versions/{id}/testcases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listTestcases
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listTestcases"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions/{id}/references": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listReferences
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listReferences"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions/{id}/testcases/{order}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * putTestcase
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        put: operations["putTestcase"];
        post?: never;
        /**
         * deleteTestcase
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        delete: operations["deleteTestcase"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions/{id}/references/{language_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * putReference
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        put: operations["putReference"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problem-versions/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * publishVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["publishVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/problems/{id}/practice-policy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * updatePracticePolicy
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updatePracticePolicy"];
        trace?: never;
    };
    "/courses/{id}/assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listAssignments
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listAssignments"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * createAssignment
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createAssignment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/assignments/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getAssignment
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getAssignment"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * updateAssignment
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updateAssignment"];
        trace?: never;
    };
    "/assignments/{id}/problems/{problem_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getAssignmentProblem
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getAssignmentProblem"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/assignments/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * publishAssignment
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["publishAssignment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/assignments/{id}/deadline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * extendDeadline
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["extendDeadline"];
        trace?: never;
    };
    "/assignments/{id}/ai-policy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * updateAiPolicy
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updateAiPolicy"];
        trace?: never;
    };
    "/submissions/{id}/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getSubmissionFeedback
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getSubmissionFeedback"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/feedback-catalogs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listFeedbackCatalogs
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listFeedbackCatalogs"];
        put?: never;
        /**
         * createFeedback
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createFeedback"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/feedback-catalogs/{id}/draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getFeedbackDraft
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getFeedbackDraft"];
        /**
         * updateFeedbackDraft
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        put: operations["updateFeedbackDraft"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/feedback-catalogs/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * publishFeedback
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["publishFeedback"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/feedback-catalogs/{id}/versions/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getFeedbackVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getFeedbackVersion"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/hint-templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listTemplateCatalogs
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listTemplateCatalogs"];
        put?: never;
        /**
         * createTemplate
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createTemplate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/hint-templates/{id}/draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getTemplateDraft
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getTemplateDraft"];
        /**
         * updateTemplateDraft
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        put: operations["updateTemplateDraft"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/hint-templates/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * publishTemplate
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["publishTemplate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/hint-templates/{id}/versions/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getTemplateVersion
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getTemplateVersion"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai-hints": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * createHint
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createHint"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai-hints/{hint_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getHint
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getHint"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai-hints/{id}/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * rateHint
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["rateHint"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/review-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listReviewItems
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listReviewItems"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listRecommendations
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listRecommendations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/practice-problems/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * getPracticeProblem
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["getPracticeProblem"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * listUsers
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        get: operations["listUsers"];
        put?: never;
        /**
         * createUser
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["createUser"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/users/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * updateUser
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        patch: operations["updateUser"];
        trace?: never;
    };
    "/admin/users/{id}/reset-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * resetPassword
         * @description 依 docs/03-api-contract.md 验证身份和对象归属；服务端裁定权限、时间和 revision。字段字节上限另按 docs/01-requirements.md 校验。
         */
        post: operations["resetPassword"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Error: {
            code: string;
            message: string;
            /** Format: uuid */
            request_id: string;
            retryable: boolean;
            retry_after_seconds: number | null;
            field_errors: {
                field: string;
                message: string;
            }[];
        };
        User: {
            /** Format: uuid */
            user_id: string;
            login_name: string;
            display_name: string;
            /** @enum {string} */
            role: "STUDENT" | "TEACHER" | "ADMIN";
            /** @enum {string} */
            status: "ACTIVE" | "DISABLED";
            must_change_password: boolean;
            revision: number;
        };
        Session: {
            authenticated: boolean;
            user: components["schemas"]["User"] | null;
            csrf_token: string;
            /** Format: date-time */
            server_time: string;
        };
        Login: {
            login_name: string;
            password: string;
        };
        LoginResult: {
            user: components["schemas"]["User"];
        };
        Password: {
            current_password: string;
            new_password: string;
        };
        Course: {
            /** Format: uuid */
            course_id: string;
            title: string;
            /** Format: uuid */
            teacher_id: string;
            /** @enum {string} */
            status: "ACTIVE" | "ARCHIVED";
            revision: number;
        };
        CreateCourse: {
            title: string;
        };
        UpdateCourse: {
            title: string;
            expected_revision: number;
        };
        Revision: {
            revision: number;
        };
        CourseCreated: {
            /** Format: uuid */
            course_id: string;
            revision: number;
        };
        Member: {
            /** Format: uuid */
            user_id: string;
            display_name: string;
            /** @enum {string} */
            status: "ACTIVE" | "DISABLED";
        };
        UpdateMember: {
            /** @enum {string} */
            status: "ACTIVE" | "DISABLED";
            expected_revision: number;
        };
        MemberUpdated: {
            /** Format: uuid */
            user_id: string;
            /** @enum {string} */
            status: "ACTIVE" | "DISABLED";
            revision: number;
        };
        Sample: {
            input: string;
            output: string;
        };
        LanguageProfile: {
            /** @enum {string} */
            language_key: "cpp17" | "python3";
            version: string;
            image_digest: string;
            cpu_time_ms: number;
            wall_time_ms: number;
        } & (unknown & unknown);
        Profile: {
            /** Format: uuid */
            profile_id: string;
            languages: components["schemas"]["LanguageProfile"][];
            /** @constant */
            memory_bytes: 268435456;
            /** @constant */
            output_bytes: 1048576;
            /** @enum {string} */
            comparison: "ASCII_TOKENS";
            /** @constant */
            directory_bytes: 33554432;
            /** @constant */
            run_entities: 1;
            /** @constant */
            compile_timeout_ms: 20000;
            /** @constant */
            compile_memory_bytes: 536870912;
            /** @constant */
            compile_entities: 30;
        };
        Problem: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            canonical_problem_id: string;
            /** Format: uuid */
            owner_course_id: string;
            practice_released: boolean;
            practice_version_id: string | null;
            revision: number;
            title: string;
            /** @enum {string} */
            status: "DRAFT" | "PUBLISHED";
        };
        CreateProblem: {
            /** Format: uuid */
            course_id: string;
            /** Format: uuid */
            canonical_problem_id?: string;
        };
        ProblemCreated: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            canonical_problem_id: string;
        };
        VersionCreated: {
            /** Format: uuid */
            version_id: string;
            revision: number;
        };
        PublishVersion: {
            expected_revision: number;
            /** Format: uuid */
            preflight_id: string;
            reason: string;
        };
        PublishedVersion: {
            /** Format: date-time */
            published_at: string;
            checksum: string;
        };
        DeleteVersion: {
            expected_revision: number;
            reason: string;
        };
        Testcase: {
            /** Format: uuid */
            testcase_id: string;
            order: number;
            input_text: string;
            answer_text: string;
            input_sha256: string;
            answer_sha256: string;
        };
        PutTestcase: {
            input_text: string;
            answer_text: string;
            expected_revision: number;
        };
        TestcaseUpdated: {
            /** Format: uuid */
            testcase_id: string;
            input_sha256: string;
            answer_sha256: string;
            revision: number;
        };
        Reference: {
            /** Format: uuid */
            reference_id: string;
            /** @enum {string} */
            language_key: "cpp17" | "python3";
            code: string;
            checksum: string;
        };
        PutReference: {
            code: string;
            expected_revision: number;
        };
        ReferenceUpdated: {
            /** Format: uuid */
            reference_id: string;
            checksum: string;
            revision: number;
        };
        RevisionCommand: {
            expected_revision: number;
        };
        PracticePolicy: {
            practice_released: boolean;
            /** Format: uuid */
            practice_version_id?: string;
            /** Format: uuid */
            canonical_problem_id: string;
            expected_revision: number;
            reason: string;
        };
        AssignmentItem: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            version_id: string;
            points: number;
        };
        AssignmentSummary: {
            /** Format: uuid */
            assignment_id: string;
            /** Format: uuid */
            course_id: string;
            title: string;
            /** Format: date-time */
            open_at: string;
            /** Format: date-time */
            due_at: string;
            /** @enum {string} */
            state: "DRAFT" | "SCHEDULED" | "OPEN" | "CLOSED" | "ARCHIVED";
            revision: number;
        };
        AssignmentCreated: {
            /** Format: uuid */
            assignment_id: string;
            revision: number;
        };
        PublishCommand: {
            expected_revision: number;
            reason: string;
        };
        AssignmentPublished: {
            /** @enum {string} */
            state: "SCHEDULED" | "OPEN" | "CLOSED";
            revision: number;
        };
        DeadlineCommand: {
            /** Format: date-time */
            new_due_at: string;
            expected_revision: number;
            reason: string;
        };
        DeadlineUpdated: {
            /** Format: date-time */
            old_due_at: string;
            /** Format: date-time */
            new_due_at: string;
            revision: number;
        };
        PolicyCommand: {
            /** @enum {string} */
            ai_policy: "DISABLED" | "GUIDED";
            expected_revision: number;
            reason: string;
        };
        FeedbackDraft: {
            title: string;
            explanation: string;
            checklist: string[];
        };
        FeedbackVersion: {
            /** Format: uuid */
            feedback_version_id: string;
            title: string;
            explanation: string;
            checklist: string[];
        };
        CreateFeedback: {
            /** @enum {string} */
            scope: "GLOBAL" | "COURSE";
            /** Format: uuid */
            course_id?: string;
            /** @enum {string} */
            verdict: "CE" | "WA" | "TLE" | "RE" | "SE";
            /** @enum {string} */
            language_key: "cpp17" | "python3" | "ALL";
            draft: components["schemas"]["FeedbackDraft"];
        };
        CatalogCreated: {
            /** Format: uuid */
            catalog_id: string;
            revision: number;
        };
        VersionPublished: {
            /** Format: uuid */
            version_id: string;
            checksum: string;
        };
        TemplateDraft: {
            body: string;
            allowed_placeholders: ("public_problem" | "public_samples" | "student_code" | "sanitized_diagnostic" | "verdict" | "question")[];
            schema_version: string;
        };
        CreateTemplate: {
            /** @enum {string} */
            scope: "GLOBAL" | "COURSE";
            /** Format: uuid */
            course_id?: string;
            draft: components["schemas"]["TemplateDraft"];
        };
        TemplateCreated: {
            /** Format: uuid */
            template_id: string;
            revision: number;
        };
        HintSections: {
            error_category: string;
            location_clues: string;
            checks: string;
            learning_advice: string;
        };
        CreateHint: {
            /** Format: uuid */
            submission_id: string;
            question?: string;
            /** @constant */
            data_sharing_consent: true;
            /** Format: uuid */
            request_key: string;
        };
        HintAccepted: {
            /** Format: uuid */
            hint_id: string;
            /** @enum {string} */
            status: "PENDING";
        };
        HintRating: {
            /** @enum {string} */
            rating: "USEFUL" | "NOT_USEFUL" | "ERROR";
            comment?: string;
        };
        HintRatingResult: {
            /** @enum {string} */
            rating: "USEFUL" | "NOT_USEFUL" | "ERROR";
        };
        ReviewItem: {
            /** Format: uuid */
            submission_id: string;
            /** Format: uuid */
            assignment_id: string;
            /** Format: uuid */
            problem_id: string;
            title: string;
            /** @enum {string} */
            verdict: "CE" | "WA" | "TLE" | "RE";
            /** @enum {string} */
            context: "FORMAL" | "PRACTICE";
            /** Format: date-time */
            accepted_at: string;
        };
        Recommendation: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            practice_version_id: string;
            title: string;
            tags: string[];
        };
        CreateUser: {
            login_name: string;
            display_name: string;
            /** @enum {string} */
            role: "STUDENT" | "TEACHER" | "ADMIN";
            initial_password: string;
            reason: string;
        };
        UpdateUser: {
            display_name?: string;
            /** @enum {string} */
            status?: "ACTIVE" | "DISABLED";
            expected_revision: number;
            reason: string;
        };
        ResetPassword: {
            one_time_password: string;
            expected_revision: number;
            reason: string;
        };
        CreateVersion: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            base_version_id?: string;
            title: string;
            statement: string;
            samples: components["schemas"]["Sample"][];
            tags: string[];
            profile: components["schemas"]["Profile"];
            source_ref: string;
        };
        UpdateVersion: {
            title?: string;
            statement?: string;
            samples?: components["schemas"]["Sample"][];
            tags?: string[];
            profile?: components["schemas"]["Profile"];
            source_ref?: string;
            expected_revision: number;
        };
        PublicProblem: {
            /** Format: uuid */
            problem_id: string;
            /** Format: uuid */
            version_id: string;
            title: string;
            statement: string;
            samples: components["schemas"]["Sample"][];
            tags: string[];
            profile: components["schemas"]["Profile"];
            source_ref: string;
        };
        ProblemVersion: {
            /** Format: uuid */
            version_id: string;
            /** Format: uuid */
            problem_id: string;
            title: string;
            statement: string;
            samples: components["schemas"]["Sample"][];
            tags: string[];
            profile: components["schemas"]["Profile"];
            source_ref: string;
            revision: number;
            published_at: string | null;
            checksum: string | null;
        };
        CreateAssignment: {
            /** Format: uuid */
            course_id: string;
            title: string;
            items: components["schemas"]["AssignmentItem"][];
            /** Format: date-time */
            open_at: string;
            /** Format: date-time */
            due_at: string;
            /** @enum {string} */
            ai_policy: "DISABLED" | "GUIDED";
        };
        UpdateAssignment: {
            /** Format: uuid */
            course_id?: string;
            title?: string;
            items?: components["schemas"]["AssignmentItem"][];
            /** Format: date-time */
            open_at?: string;
            /** Format: date-time */
            due_at?: string;
            /** @enum {string} */
            ai_policy?: "DISABLED" | "GUIDED";
            expected_revision: number;
        };
        AssignmentView: {
            /** Format: uuid */
            assignment_id: string;
            /** Format: uuid */
            course_id: string;
            title: string;
            /** Format: date-time */
            open_at: string;
            /** Format: date-time */
            due_at: string;
            /** @enum {string} */
            state: "DRAFT" | "SCHEDULED" | "OPEN" | "CLOSED" | "ARCHIVED";
            revision: number;
            /** Format: date-time */
            server_time: string;
            items: {
                /** Format: uuid */
                problem_id: string;
                title: string;
                points: number;
            }[];
            /** @enum {string} */
            ai_policy: "DISABLED" | "GUIDED";
            /** @enum {string} */
            fairness_review: "NONE" | "PENDING" | "RESOLVED";
            fairness_notice: string | null;
            /** @enum {string} */
            grade_state: "PROVISIONAL" | "PENDING" | "PUBLISHED" | "REJUDGING";
        };
        UpdateFeedback: {
            title: string;
            explanation: string;
            checklist: string[];
            expected_revision: number;
        };
        FeedbackDraftView: {
            /** Format: uuid */
            catalog_id: string;
            title: string;
            explanation: string;
            checklist: string[];
            revision: number;
        };
        CatalogSummary: {
            /** Format: uuid */
            catalog_id: string;
            /** @enum {string} */
            scope: "GLOBAL" | "COURSE";
            course_id: string | null;
            title: string;
            revision: number;
        };
        UpdateTemplate: {
            body: string;
            allowed_placeholders: ("public_problem" | "public_samples" | "student_code" | "sanitized_diagnostic" | "verdict" | "question")[];
            schema_version: string;
            expected_revision: number;
        };
        TemplateDraftView: {
            /** Format: uuid */
            template_id: string;
            body: string;
            allowed_placeholders: ("public_problem" | "public_samples" | "student_code" | "sanitized_diagnostic" | "verdict" | "question")[];
            schema_version: string;
            revision: number;
        };
        TemplateVersion: {
            /** Format: uuid */
            version_id: string;
            body: string;
            allowed_placeholders: ("public_problem" | "public_samples" | "student_code" | "sanitized_diagnostic" | "verdict" | "question")[];
            schema_version: string;
            checksum: string;
        };
        TemplateSummary: {
            /** Format: uuid */
            template_id: string;
            /** @enum {string} */
            scope: "GLOBAL" | "COURSE";
            course_id: string | null;
            revision: number;
        };
        HintView: {
            /** Format: uuid */
            hint_id: string;
            /** Format: uuid */
            submission_id: string;
            /** @enum {string} */
            status: "PENDING" | "READY" | "FAILED" | "BLOCKED";
            reason_code: string | null;
            model_version: string | null;
            /** Format: uuid */
            template_version_id: string;
            sections: components["schemas"]["HintSections"] | null;
            fallback_feedback: components["schemas"]["FeedbackVersion"] | null;
            /** Format: date-time */
            created_at: string;
        };
        CoursePage: {
            items: components["schemas"]["Course"][];
            next_cursor: string | null;
        };
        MemberPage: {
            items: components["schemas"]["Member"][];
            next_cursor: string | null;
        };
        ProblemPage: {
            items: components["schemas"]["Problem"][];
            next_cursor: string | null;
        };
        AssignmentSummaryPage: {
            items: components["schemas"]["AssignmentSummary"][];
            next_cursor: string | null;
        };
        TestcasePage: {
            items: components["schemas"]["Testcase"][];
            next_cursor: string | null;
        };
        ReferencePage: {
            items: components["schemas"]["Reference"][];
            next_cursor: string | null;
        };
        CatalogSummaryPage: {
            items: components["schemas"]["CatalogSummary"][];
            next_cursor: string | null;
        };
        TemplateSummaryPage: {
            items: components["schemas"]["TemplateSummary"][];
            next_cursor: string | null;
        };
        ReviewItemPage: {
            items: components["schemas"]["ReviewItem"][];
            next_cursor: string | null;
        };
        UserPage: {
            items: components["schemas"]["User"][];
            next_cursor: string | null;
        };
        Recommendations: {
            items: components["schemas"]["Recommendation"][];
        };
    };
    responses: {
        /** @description 请求格式无效 */
        Error400: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "INVALID_REQUEST",
                 *       "message": "请求格式无效",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 请重新登录 */
        Error401: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "UNAUTHENTICATED",
                 *       "message": "请重新登录",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 没有操作权限 */
        Error403: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "FORBIDDEN",
                 *       "message": "没有操作权限",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 内容不可用 */
        Error404: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "NOT_FOUND",
                 *       "message": "内容不可用",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 内容已变更，请重新载入 */
        Error409: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "REVISION_CONFLICT",
                 *       "message": "内容已变更，请重新载入",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 内容超过字节上限 */
        Error413: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "CONTEXT_TOO_LARGE",
                 *       "message": "内容超过字节上限",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 请检查输入 */
        Error422: {
            headers: {
                "X-Request-Id"?: string;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "VALIDATION_ERROR",
                 *       "message": "请检查输入",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": false,
                 *       "retry_after_seconds": null,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 今日提示次数已用完 */
        Error429: {
            headers: {
                "X-Request-Id"?: string;
                "Retry-After"?: number;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "AI_DAILY_QUOTA",
                 *       "message": "今日提示次数已用完",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": true,
                 *       "retry_after_seconds": 5,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description 服务暂不可用 */
        Error503: {
            headers: {
                "X-Request-Id"?: string;
                "Retry-After"?: number;
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "code": "AI_UNAVAILABLE",
                 *       "message": "服务暂不可用",
                 *       "request_id": "11111111-1111-4111-8111-111111111111",
                 *       "retryable": true,
                 *       "retry_after_seconds": 5,
                 *       "field_errors": []
                 *     }
                 */
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getSession: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    login: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Login"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoginResult"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    logout: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            204: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    changePassword: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Password"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            204: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listCourses: {
        parameters: {
            query?: {
                status?: "ACTIVE" | "ARCHIVED";
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CoursePage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createCourse: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateCourse"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CourseCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getCourse: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Course"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateCourse: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateCourse"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listMembers: {
        parameters: {
            query?: {
                status?: "ACTIVE" | "DISABLED";
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateMember: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateMember"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberUpdated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listProblems: {
        parameters: {
            query?: {
                status?: "DRAFT" | "PUBLISHED";
                tag?: string;
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createProblem: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateProblem"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createVersion: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateVersion"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getVersion: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemVersion"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    deleteVersion: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteVersion"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            204: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateVersion: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateVersion"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listTestcases: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TestcasePage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listReferences: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReferencePage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    putTestcase: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
                order: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PutTestcase"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TestcaseUpdated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    deleteTestcase: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
                order: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            204: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    putReference: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
                language_key: "cpp17" | "python3";
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PutReference"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReferenceUpdated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    publishVersion: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishVersion"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublishedVersion"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updatePracticePolicy: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PracticePolicy"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listAssignments: {
        parameters: {
            query?: {
                state?: "DRAFT" | "SCHEDULED" | "OPEN" | "CLOSED" | "ARCHIVED";
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentSummaryPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createAssignment: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateAssignment"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getAssignment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentView"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateAssignment: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateAssignment"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getAssignmentProblem: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
                problem_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicProblem"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    publishAssignment: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentPublished"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    extendDeadline: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeadlineCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeadlineUpdated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateAiPolicy: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PolicyCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getSubmissionFeedback: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackVersion"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listFeedbackCatalogs: {
        parameters: {
            query?: {
                course_id?: string;
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogSummaryPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createFeedback: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateFeedback"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getFeedbackDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackDraftView"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateFeedbackDraft: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateFeedback"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    publishFeedback: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionPublished"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getFeedbackVersion: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
                version: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackVersion"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listTemplateCatalogs: {
        parameters: {
            query?: {
                course_id?: string;
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateSummaryPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createTemplate: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateTemplate"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateCreated"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getTemplateDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateDraftView"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateTemplateDraft: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateTemplate"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    publishTemplate: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishCommand"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionPublished"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getTemplateVersion: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
                version: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateVersion"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createHint: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateHint"];
            };
        };
        responses: {
            /** @description 终态同键重放，复验当前权限 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HintView"];
                };
            };
            /** @description 成功；仅返回当前身份可见字段 */
            202: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HintAccepted"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getHint: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                hint_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HintView"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    rateHint: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HintRating"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HintRatingResult"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listReviewItems: {
        parameters: {
            query: {
                course_id?: string;
                context: "FORMAL" | "PRACTICE";
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewItemPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listRecommendations: {
        parameters: {
            query?: {
                course_id?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Recommendations"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    getPracticeProblem: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicProblem"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    listUsers: {
        parameters: {
            query?: {
                login_name?: string;
                role?: "STUDENT" | "TEACHER" | "ADMIN";
                status?: "ACTIVE" | "DISABLED";
                limit?: number;
                cursor?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserPage"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    createUser: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateUser"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            201: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["User"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    updateUser: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateUser"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            200: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Revision"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
    resetPassword: {
        parameters: {
            query?: never;
            header: {
                "X-CSRF-Token": string;
                /** @description Browser supplies Origin automatically; server MUST validate it for all writes including login. */
                Origin?: string;
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetPassword"];
            };
        };
        responses: {
            /** @description 成功；仅返回当前身份可见字段 */
            204: {
                headers: {
                    "X-Request-Id"?: string;
                    "Cache-Control"?: "no-store";
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            413: components["responses"]["Error413"];
            422: components["responses"]["Error422"];
            429: components["responses"]["Error429"];
            503: components["responses"]["Error503"];
        };
    };
}
