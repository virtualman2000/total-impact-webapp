angular.module( 'infopages', [
    'security',
    'services.page',
    'services.tiMixpanel',
    'directives.fullscreen'
  ])
  .factory("InfoPages", function ($http) {
    var getProvidersInfo = function () {
      return $http.get("/providers").then(
        function (resp) {
          return _.filter(resp.data, function (provider) {
            // only show providers with a description
            return !!provider.descr
          })
        },
        function (resp) {
          console.log("/providers failed.")
        }
      )
    }
    return {
      'getProvidersInfo': getProvidersInfo
    }
  })

  .config(['$routeProvider', function($routeProvider, InfoPages, security) {
    $routeProvider

      .when('/', {
        templateUrl: 'infopages/landing.tpl.html',
        controller: 'landingPageCtrl',
        resolve:{
          allowed: function(security){
            return security.testUserAuthenticationLevel("loggedIn", false)
          }
        }
      })
      .when('/h-index', {
        templateUrl: 'infopages/landing.tpl.html',
        controller: 'hIndexLandingPageCtrl',
        resolve:{
          allowed: function(security){
            return security.testUserAuthenticationLevel("loggedIn", false)
          }
        }
      })
      .when('/open-science', {
        templateUrl: 'infopages/landing.tpl.html',
        controller: 'openScienceLandingPageCtrl',
        resolve:{
          allowed: function(security){
            return security.testUserAuthenticationLevel("loggedIn", false)
          }
        }
      })
      .when('/faq', {
        templateUrl: 'infopages/faq.tpl.html',
        controller: 'faqPageCtrl'
      })
      .when('/legal', {
        templateUrl: 'infopages/legal.tpl.html',
        controller: 'legalPageCtrl'
      })
      .when('/metrics', {
        templateUrl: 'infopages/metrics.tpl.html',
        controller: 'metricsPageCtrl',
        resolve: {
          providersInfo: function(InfoPages){
            return InfoPages.getProvidersInfo()
          }
        }
      })
      .when('/about', {
        templateUrl: 'infopages/about.tpl.html',
        controller: 'aboutPageCtrl'
      })
      .when('/advisors', {
        templateUrl: 'infopages/advisors.tpl.html',
        controller: 'advisorsPageCtrl'
      })
      .when('/spread-the-word', {
        templateUrl: 'infopages/spread-the-word.tpl.html',
        controller: 'SpreadTheWordCtrl'
      })
      .when('/collection/:cid', {
        templateUrl: 'infopages/collection.tpl.html',
        controller: 'collectionPageCtrl'
      })
      .when('/item/*', {
        templateUrl: 'infopages/collection.tpl.html',
        controller: 'collectionPageCtrl'
      })
  }])

  .controller( 'landingPageCtrl', function landingPageCtrl ( $scope, Page, TiMixpanel ) {
//    TiMixpanel.registerOnce({
//      "selling points": _.sample([
//        "impacts, products, free",
//        "impacts, products, notifications"
//      ])
//    })

    TiMixpanel.track("viewed landing page")
    var signupFormShowing = false
    $scope.landingPageType = "main"
    Page.setName("landing")
    Page.setInfopage(true)
    Page.setTitle("Share the full story of your research impact.")

  })

  .controller("hIndexLandingPageCtrl", function($scope, Page){
    $scope.landingPageType = "h-index"
    Page.setName("landing")
    Page.setInfopage(true)
    Page.setTitle("Share the full story of your research impact.")
  })

  .controller("openScienceLandingPageCtrl", function($scope, Page){
    $scope.landingPageType = "open-science"
    Page.setInfopage(true)
    Page.setTitle("Share the full story of your research impact.")
  })

  .controller( 'faqPageCtrl', function faqPageCtrl ( $scope, $window, Page) {
    $window.scrollTo(0, 0)
    Page.setTitle("FAQ")
    Page.setInfopage(true)
  })

  .controller( 'legalPageCtrl', function faqPageCtrl ( $scope, $window, Page) {
    $window.scrollTo(0, 0)
    Page.setTitle("Legal")
    Page.setInfopage(true)
  })

  .controller( 'metricsPageCtrl', function faqPageCtrl ( $scope,$window, Page, providersInfo) {
    $window.scrollTo(0, 0)
    Page.setTitle("Metrics")
    Page.setInfopage(true)
    $scope.providers = providersInfo
    console.log("metrics page controller running")
  })

  .controller( 'aboutPageCtrl', function aboutPageCtrl ( $scope, $window, Page ) {
    $window.scrollTo(0, 0)
    Page.setTitle("about")
    Page.setInfopage(true)

  })

  .controller('advisorsPageCtrl', function($scope, $window,Page) {
    $window.scrollTo(0, 0)
    Page.setTitle("advisors")
    Page.setInfopage(true)

  })
  .controller('SpreadTheWordCtrl', function($scope, $window,Page) {
    $window.scrollTo(0, 0)
    Page.setTitle("Spread the word")
    Page.setInfopage(true)

  })

  .controller( 'collectionPageCtrl', function aboutPageCtrl ( $scope, $window,Page ) {
    Page.setTitle("Collections are retired")
    Page.setInfopage(true)

  });

